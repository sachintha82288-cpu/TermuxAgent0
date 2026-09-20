"""The interactive REPL — banner, status bar, slash commands, ```run blocks."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import Config, session_path, storage_home
from .history import load_history, save_history
from .llm import LLMError, list_models
from .theme import (THEMES, box, gradient_text, paint, print_banner, rule,
                    set_theme, term_width)
from .tools import READ_ONLY, summarize
from .ui import Spinner, confirm, dim, error, info, select, success, warn

try:  # nicer input: up-arrow history
    import readline  # noqa: F401
    _HAS_READLINE = True
except ImportError:  # pragma: no cover
    _HAS_READLINE = False

HELP = """{sec}commands{r}
  {acc}/help{r}          this list
  {acc}/new{r}           start a fresh conversation
  {acc}/save{r}          export the chat to ~/termux-agent-chats/*.md
  {acc}/theme{r} [name]  change theme {mut}({themes}){r}
  {acc}/provider{r}      switch API provider (27 built in)
  {acc}/model{r} [name]  switch model  {mut}(current: {model}){r}
  {acc}/models{r}        list models from the API
  {acc}/tools{r}         toggle agent tools on/off
  {acc}/auto{r}          toggle auto-approve for shell/write actions
  {acc}/system{r} [txt]  show or set extra system instructions
  {acc}/stats{r}         session stats
  {acc}/clear{r}         clear the screen
  {acc}/exit{r}          quit  {mut}(Ctrl+C or Ctrl+D also work){r}

{sec}shortcuts{r}
  {acc}!command{r}       run a shell command directly, e.g. {mut}!ls -la{r}
  {acc}Ctrl+C{r}         stop the current answer · twice = exit
  {mut}Everything else goes to the AI. Ask in any language.{r}"""

RUN_BLOCK = re.compile(r"```run\n(.*?)```", re.S)


def _input_history_file() -> str:
    return str(storage_home() / "input-history")


def _save_input_history() -> None:
    if _HAS_READLINE:
        try:
            hist = _input_history_file()
            os.makedirs(os.path.dirname(hist), exist_ok=True)
            readline.read_history_file(hist)
        except OSError:
            pass


def _flush_input_history() -> None:
    if _HAS_READLINE:
        try:
            readline.set_history_length(500)
            readline.write_history_file(_input_history_file())
        except OSError:
            pass


class Repl:
    def __init__(self, cfg: Config, resume: bool = False,
                 yes: bool = False) -> None:
        self.cfg = cfg
        self.resume = resume
        self.yes = yes
        self.auto = cfg.data["auto_approve"]
        self._content_started = False

    # ------------------------------------------------------------------ ui
    def _print_stream(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def _print_reasoning(self, text: str) -> None:
        sys.stdout.write(paint(text, "muted", dim=True, italic=True))
        sys.stdout.flush()

    def _announce(self, name: str, args: dict) -> None:
        if self._content_started:
            print()
            self._content_started = False
        print("  " + paint("🔧", "accent") + " " +
              paint(name, "accent", bold=True) + " " +
              paint(summarize(name, args), "muted"))

    def _approve(self, name: str, args: dict) -> bool:
        if self.yes:
            return True
        print()
        print(box([paint(summarize(name, args), "warn")],
                  title=f"approve {name}?", color="warn", style="heavy"))
        return confirm("run it?", default=True)

    # ------------------------------------------------------------------ run
    def run(self) -> None:
        from .agent import Agent

        set_theme(self.cfg.data["theme"])
        print_banner(f"v{__version__} · your terminal's AI")
        print()
        print(self._status_bar())
        if self._is_first_chat():
            print()
            print(box([
                paint("Try one of these — just type it:", "secondary", bold=True),
                "  • what's my battery level?",
                "  • create a python project in this folder",
                "  • update packages and install git",
                "  • show the 5 largest files in ~/storage/downloads",
                "",
                paint("/help = commands · !cmd = shell · Ctrl+C ×2 = exit", "muted"),
            ], title="tips", color="accent"))
        else:
            print(paint("  /help for commands · type anything to start", "muted"))
        print()

        agent = Agent(self.cfg, on_content=self._print_stream,
                      on_reasoning=self._print_reasoning,
                      approve=self._approve, announce=self._announce,
                      tools_on=self.cfg.tools_enabled() or None)
        agent.new_session()
        if self.resume:
            old = load_history()
            if old:
                agent.load_messages(old)
                info(f"resumed {len(old)} messages from last session")

        _save_input_history()
        interrupted_once = False
        try:
            while True:
                try:
                    line = input(paint("you ❯ ", "secondary", bold=True))
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    # first Ctrl+C at the prompt just clears the line (phone
                    # keyboards make it easy to hit by accident)
                    print()
                    if interrupted_once:
                        break
                    interrupted_once = True
                    print(paint("  (Ctrl+C again or /exit to quit)", "muted"))
                    continue
                interrupted_once = False
                line = line.strip()
                if not line:
                    continue
                if line.startswith("/"):
                    if self._command(line, agent):
                        break
                    continue
                if line.startswith("!"):
                    self._bang(line[1:].strip())
                    continue
                self._send(agent, line)
        finally:
            _flush_input_history()
            self._goodbye(agent)

    def _is_first_chat(self) -> bool:
        flag = storage_home() / ".welcomed"
        if flag.exists():
            return False
        try:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text("1")
        except OSError:
            pass
        return True

    # ------------------------------------------------------------------ send
    def _send(self, agent, text: str) -> None:
        spinner = Spinner("thinking")
        spinner.start()
        printed = {"any": False}

        def content(chunk: str) -> None:
            spinner.stop()  # first token arrived — hand over to live text
            printed["any"] = True
            self._content_started = True
            self._print_stream(chunk)

        agent.on_content = content

        def reasoning(chunk: str) -> None:
            spinner.stop()
            self._print_reasoning(chunk)

        agent.on_reasoning = reasoning if self.cfg.data["show_reasoning"] else None
        try:
            reply = agent.chat(text)
        except LLMError as exc:
            spinner.stop()
            if self._content_started:
                print()
            error(str(exc))
            self._hint_for_error(str(exc))
            return
        except KeyboardInterrupt:
            spinner.stop()
            print()
            warn("interrupted (partial turn kept in history).")
            return
        spinner.stop()
        if printed["any"]:
            print()
        else:
            self._print_stream(reply or "")
            print()
        self._offer_run_blocks(reply or "")
        print(rule(color="muted"))
        print()

    def _hint_for_error(self, msg: str) -> None:
        low = msg.lower()
        if "401" in low or "invalid api key" in low:
            warn("Looks like a bad API key → re-enter it via /provider or 'agent setup'.")
        elif "429" in low or "rate limit" in low:
            warn("Rate limited → wait a moment and retry, or pick another model with /model.")
        elif "404" in low or "422" in low:
            warn("The model name looks wrong → check /models and pick one with /model.")
        elif "cannot reach" in low or "timed out" in low or "connection" in low:
            if self.cfg.provider.get("needs_key") is False:
                warn("Is the local server running? (ollama serve / LM Studio server)")
            else:
                warn("Check your internet connection · run 'agent doctor' to diagnose.")
        else:
            warn("try /provider to switch APIs, or 'agent doctor' to diagnose.")

    def _offer_run_blocks(self, reply: str) -> None:
        """Providers without function calling: offer to run ```run blocks."""
        if self.cfg.tools_enabled():
            return
        blocks = RUN_BLOCK.findall(reply)
        if not blocks:
            return
        for cmd in blocks:
            cmd = cmd.strip()
            print()
            print(box([paint(cmd, "warn")], title="run?", color="warn"))
            if confirm("run it?", default=True):
                import subprocess
                try:
                    proc = subprocess.run(cmd, shell=True)
                    info(f"(exit code {proc.returncode})")
                except KeyboardInterrupt:
                    warn("interrupted.")

    def _bang(self, cmd: str) -> None:
        if not cmd:
            return
        import subprocess
        print(paint(f"$ {cmd}", "muted"))
        try:
            proc = subprocess.run(cmd, shell=True)
            info(f"(exit code {proc.returncode})")
        except KeyboardInterrupt:
            warn("interrupted.")

    # ------------------------------------------------------------------ cmds
    def _status_bar(self) -> str:
        p = self.cfg.provider
        tools = paint("tools on", "ok") if self.cfg.tools_enabled() \
            else paint("tools off", "warn")
        auto = paint("auto-approve", "warn") if self.auto else paint("ask-first", "ok")
        bar = (paint("┌─ ", "primary") +
               "\033[1m" + gradient_text(p["name"]) + "\033[0m" +
               paint(" ─┄ ", "muted") + paint(self.cfg.model() or "?", "secondary") +
               paint(" ─┄ ", "muted") + tools +
               paint(" ─┄ ", "muted") + auto +
               paint(" ─┄ ", "muted") + paint(self.cfg.data["theme"], "accent") +
               paint(" ─", "primary"))
        from .theme import truncate
        return truncate(bar, max(term_width(), 20))

    def _command(self, line: str, agent) -> bool:
        """Handle a /command.  Returns True when the REPL should exit."""
        from .setup import run_setup
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            return True
        if cmd == "/help":
            print(HELP.format(sec=paint("─", "primary"), acc=paint("•", "accent"),
                              mut=paint("", "muted"), r=paint("", "muted"),
                              themes="/".join(list(THEMES)[:4]) + "…",
                              model=self.cfg.model()))
        elif cmd == "/new":
            agent.reset()
            success("fresh conversation started.")
        elif cmd == "/save":
            self._export(agent)
        elif cmd == "/theme":
            self._theme_cmd(arg)
            print(self._status_bar())
        elif cmd == "/provider":
            self._provider_cmd(agent)
        elif cmd == "/model":
            if arg:
                self.cfg.set_model(self.cfg.provider_id, arg)
                self.cfg.save()
                success(f"model → {arg}")
            else:
                self._model_picker(agent)
        elif cmd == "/models":
            self._list_models()
        elif cmd == "/tools":
            self.cfg.data["tools"] = not self.cfg.data["tools"]
            self.cfg.save()
            agent.tools_on = self.cfg.tools_enabled()
            agent.new_session()
            success(f"tools {'ON' if agent.tools_on else 'OFF'}")
        elif cmd == "/auto":
            self.auto = not self.auto
            self.cfg.data["auto_approve"] = self.auto
            self.cfg.save()
            state = paint("ON — no confirmation prompts", "warn") if self.auto \
                else paint("OFF — shell/write actions ask first", "ok")
            info(f"auto-approve {state}")
        elif cmd == "/system":
            if arg:
                self.cfg.data["system_extra"] = arg
                self.cfg.save()
                agent.new_session()
                success("extra system instructions updated.")
            else:
                cur = self.cfg.data["system_extra"] or "(none)"
                print(box([cur], title="extra system instructions"))
        elif cmd == "/stats":
            n_msgs = len(agent.messages) - 1
            usage = agent.usage_total
            print(box([
                f"messages this session: {n_msgs}",
                f"~tokens used:          {usage['completion_tokens']}",
                f"provider:              {self.cfg.provider['name']}",
                f"model:                 {self.cfg.model()}",
            ], title="stats"))
        elif cmd == "/clear":
            os.system("clear 2>/dev/null || cls 2>/dev/null")
            print_banner(f"v{__version__}")
            print(self._status_bar())
            print()
        else:
            warn(f"unknown command: {cmd} — try /help")
        print()
        return False

    def _provider_cmd(self, agent) -> None:
        from .setup import _enter_key, _pick_model, _pick_provider
        from .ui import ask
        p = _pick_provider(self.cfg)
        if not p:
            return
        self.cfg.data["provider"] = p["id"]
        if p["id"] == "custom" and not self.cfg.base_url():
            url = ask("Base URL (e.g. http://192.168.1.5:8080/v1)", "").strip()
            self.cfg.data["custom_base_urls"]["custom"] = url.rstrip("/")
        if p.get("needs_key") is not False and not self.cfg.api_key():
            if not _enter_key(self.cfg, p):
                warn("no key — chat will fail until you add one (/provider again).")
        if not self.cfg.model():
            model = _pick_model(self.cfg, p, test_key=bool(self.cfg.api_key()))
            if model:
                self.cfg.set_model(p["id"], model)
        self.cfg.save()
        agent.tools_on = self.cfg.tools_enabled()
        agent.new_session()
        success(f"provider → {p['name']} · model {self.cfg.model() or '(pick with /model)'}")
        print(self._status_bar())

    def _theme_cmd(self, arg: str) -> None:
        names = list(THEMES)
        if arg and arg in THEMES:
            chosen = arg
        else:
            from .theme import banner

            def preview(idx: int) -> List[str]:
                set_theme(names[idx])
                return banner("AGENT", "", "")[:7] + [paint(f"theme: {names[idx]}", "muted")]

            idx = select("theme", names, index=names.index(self.cfg.data["theme"]) if self.cfg.data["theme"] in names else 0,
                         preview=preview)
            if idx is None:
                set_theme(self.cfg.data["theme"])  # undo the preview
                return
            chosen = names[idx]
        self.cfg.data["theme"] = chosen
        self.cfg.save()
        set_theme(chosen)
        success(f"theme → {chosen}")

    def _model_picker(self, agent) -> None:
        with Spinner(f"fetching models from {self.cfg.provider['name']}"):
            try:
                models = list_models(self.cfg.base_url(), self.cfg.api_key(),
                                     headers=self.cfg.headers())
            except LLMError as exc:
                models = []
                warn(str(exc))
        if not models:
            models = list(self.cfg.provider.get("models") or [])
            if self.cfg.model() and self.cfg.model() not in models:
                models.insert(0, self.cfg.model())
        if not models:
            warn("no model list — use /model <name>")
            return
        idx0 = models.index(self.cfg.model()) if self.cfg.model() in models else 0
        idx = select("model", models[:40], index=idx0)
        if idx is None:
            return
        self.cfg.set_model(self.cfg.provider_id, models[idx])
        self.cfg.save()
        agent.new_session()
        success(f"model → {models[idx]}")

    def _list_models(self) -> None:
        with Spinner("loading models"):
            try:
                models = list_models(self.cfg.base_url(), self.cfg.api_key(),
                                     headers=self.cfg.headers())
            except LLMError as exc:
                error(str(exc))
                return
        info(f"{len(models)} models on {self.cfg.provider['name']}:")
        cur = self.cfg.model()
        for m in models[:60]:
            mark = paint(" ❯", "accent", bold=True) if m == cur else "  "
            print(f"{mark} {m}")
        if len(models) > 60:
            dim(f"... {len(models) - 60} more")

    # ------------------------------------------------------------------ exit
    def _export(self, agent) -> None:
        out_dir = Path.home() / "termux-agent-chats"
        out_dir.mkdir(exist_ok=True)
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
        path = out_dir / f"chat-{stamp}.md"
        try:
            path.write_text(agent.export_markdown(), encoding="utf-8")
            success(f"saved → {path}")
        except OSError as exc:
            error(f"could not save: {exc}")

    def _goodbye(self, agent) -> None:
        if self.cfg.data["history"]:
            try:
                save_history(agent.messages)
                session_path().write_text(json.dumps(agent.messages, ensure_ascii=False),
                                          encoding="utf-8")
            except (OSError, TypeError):
                pass
        print()
        print(paint("  bye! 👋  history saved — start with 'agent -c' to continue.",
                    "muted"))
        print()


def run_repl(cfg: Config, resume: bool = False) -> None:
    Repl(cfg, resume=resume).run()
