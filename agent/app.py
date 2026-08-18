"""REPL application for TermuxAgent0."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .llm import LLMClient

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich import box
    _HAS_RICH = True
except ImportError:  # graceful fallback if rich isn't installed
    _HAS_RICH = False

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    _HAS_PT = True
except ImportError:
    _HAS_PT = False


BANNER = r"""
  _____                    _                 _     ___
 |_   _|__ _ __ _ __ ___  | |    _   _  __ _| |__ / _ \ _   _  ___ _ __
   | |/ _ \ '__| '_ ` _ \ | |   | | | |/ _` | '_ \ | | | | | |/ _ \ '_ \
   | |  __/ |  | | | | | || |___| |_| | (_| | | | | |_| | |_| |  __/ | | |
   |_|\___|_|  |_| |_| |_||______\__,_|\__,_|_| |_|\___/ \__,_|\___|_| |_|
"""

SLASH_COMMANDS = {
    "/help": "Show available slash commands.",
    "/clear": "Clear the conversation context (start fresh).",
    "/history": "Print how many messages are in the current context.",
    "/model <name>": "Switch model for this session.",
    "/save <name>": "Save the current conversation to ~/.termux_agent/saves/<name>.json.",
    "/load <name>": "Load a previously saved conversation.",
    "/exit": "Exit (also Ctrl-D or Ctrl-C).",
    "/quit": "Exit.",
}


class TermuxAgentApp:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        system_prompt: str,
        config_dir: Path,
        stream: bool = True,
    ) -> None:
        self.config_dir = Path(config_dir).expanduser()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        (self.config_dir / "saves").mkdir(exist_ok=True)

        self.history_file = self.config_dir / "history.json"
        self.console = Console() if _HAS_RICH else None
        self.history: list[dict] = []

        self.client = LLMClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            stream=stream,
            system_prompt=system_prompt,
        )

    # ---------- Setup wizard ----------
    def run_setup_wizard(self) -> None:
        print("🛠  TermuxAgent0 setup")
        print("---------------------")
        print(f"Config directory: {self.config_dir}\n")

        def _ask(prompt: str, default: str = "") -> str:
            if _HAS_RICH:
                return Prompt.ask(prompt, default=default)
            d = f" [{default}]" if default else ""
            val = input(f"{prompt}{d}: ").strip()
            return val or default

        api_key = _ask("OpenAI API key (or key for your compatible endpoint)", "")
        base_url = _ask("Base URL", self.client.base_url)
        model = _ask("Model name", self.client.model)

        cfg_path = self.config_dir / "config.json"
        cfg_path.write_text(json.dumps({
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }, indent=2), encoding="utf-8")
        os_chmod_600(cfg_path)
        print(f"\n✅ Saved config to {cfg_path}")
        print("Run: python main.py")

    # ---------- One-shot mode ----------
    def run_once(self, prompt: str) -> int:
        self.history.append({"role": "user", "content": prompt})
        try:
            answer = self.client.chat(self.history, on_token=self._emit_token)
        except Exception as e:  # noqa: BLE001
            print(f"\n[!] Error: {e}", file=sys.stderr)
            return 1
        if not self.client.stream:
            self._render_answer(answer)
        self._save_history()
        return 0

    # ---------- REPL mode ----------
    def run_repl(self) -> int:
        self._load_history()
        self._print_banner()

        session = None
        if _HAS_PT:
            hist_file = self.config_dir / "repl_history.txt"
            session = PromptSession(history=FileHistory(str(hist_file)))

        while True:
            try:
                if session is not None:
                    user_input = session.prompt("\n🤖 you> ").strip()
                else:
                    print("\n🤖 you> ", end="", flush=True)
                    user_input = sys.stdin.readline().strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Bye!")
                self._save_history()
                return 0

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_slash(user_input):
                    continue

            self.history.append({"role": "user", "content": user_input})
            try:
                if self.console:
                    self.console.print("\n[bold green]agent0[/bold green] ", end="")
                else:
                    print("\nagent0 ", end="", flush=True)

                collected: list[str] = []
                answer = self.client.chat(self.history, on_token=lambda t: collected.append(t))
                # If streaming, we've already printed; add a newline.
                # If not, render full markdown.
                if not self.client.stream:
                    self._render_answer(answer)
                else:
                    print()  # final newline after streamed text
            except Exception as e:  # noqa: BLE001
                # Roll back the user turn so the context stays clean
                if self.history and self.history[-1].get("role") == "user":
                    self.history.pop()
                if self.console:
                    self.console.print(f"\n[red][!] Error:[/red] {e}")
                else:
                    print(f"\n[!] Error: {e}", file=sys.stderr)
                continue

            # Keep history trimmed
            self._trim_history()
            self._save_history()

    # ---------- helpers ----------
    def _emit_token(self, t: str) -> None:
        if self.client.stream:
            if self.console:
                self.console.print(t, end="", highlight=False)
            else:
                print(t, end="", flush=True)

    def _render_answer(self, answer: str) -> None:
        if self.console and answer:
            try:
                self.console.print(Markdown(answer))
            except Exception:
                self.console.print(answer)
        elif answer:
            print(answer)

    def _print_banner(self) -> None:
        if self.console:
            self.console.print(BANNER, style="bold cyan")
            self.console.print(
                Panel.fit(
                    f"[bold]model:[/bold] {self.client.model}   "
                    f"[bold]endpoint:[/bold] {self.client.base_url}\n"
                    f"[bold]history:[/bold] {len(self.history)} msgs   "
                    f"type [green]/help[/green] for commands",
                    box=box.ROUNDED,
                    border_style="cyan",
                )
            )
        else:
            print(BANNER)
            print(f"model: {self.client.model} | endpoint: {self.client.base_url}")
            print("Type /help for commands.")

    def _handle_slash(self, text: str) -> bool:
        parts = text.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            if self.console:
                self.console.print("👋 Bye!")
            else:
                print("👋 Bye!")
            self._save_history()
            sys.exit(0)
        elif cmd == "/help":
            if self.console:
                self.console.print("[bold]Commands:[/bold]")
                for k, v in SLASH_COMMANDS.items():
                    self.console.print(f"  [green]{k}[/green] — {v}")
            else:
                print("Commands:")
                for k, v in SLASH_COMMANDS.items():
                    print(f"  {k} - {v}")
        elif cmd == "/clear":
            self.history = []
            self._save_history()
            msg = "🧹 Conversation cleared."
            self.console.print(msg) if self.console else print(msg)
        elif cmd == "/history":
            msg = f"📜 {len(self.history)} messages in context."
            self.console.print(msg) if self.console else print(msg)
        elif cmd == "/model":
            if not arg:
                msg = f"Current model: {self.client.model}"
                self.console.print(msg) if self.console else print(msg)
            else:
                self.client.model = arg
                msg = f"✅ Model set to {arg}"
                self.console.print(msg) if self.console else print(msg)
        elif cmd == "/save":
            name = arg or "default"
            path = self.config_dir / "saves" / f"{name}.json"
            path.write_text(json.dumps(self.history, indent=2, ensure_ascii=False), encoding="utf-8")
            msg = f"💾 Saved to {path}"
            self.console.print(msg) if self.console else print(msg)
        elif cmd == "/load":
            name = arg or "default"
            path = self.config_dir / "saves" / f"{name}.json"
            if not path.exists():
                msg = f"[!] No save named '{name}'."
                self.console.print(msg, style="red") if self.console else print(msg)
            else:
                self.history = json.loads(path.read_text(encoding="utf-8"))
                msg = f"📂 Loaded {len(self.history)} messages from {path}"
                self.console.print(msg) if self.console else print(msg)
        else:
            msg = f"[!] Unknown command: {cmd} (try /help)"
            self.console.print(msg, style="red") if self.console else print(msg)
        return True

    def _trim_history(self, max_turns: int = 40) -> None:
        # Keep system prompt out of history; we prepend it per request.
        # Truncate oldest user/assistant pairs when too long.
        if len(self.history) > max_turns * 2:
            # Drop from the front until we hit a user turn
            while self.history and self.history[0]["role"] != "user":
                self.history.pop(0)
            while len(self.history) > max_turns * 2:
                self.history.pop(0)

    def _save_history(self) -> None:
        try:
            self.history_file.write_text(
                json.dumps(self.history, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_history(self) -> None:
        if self.history_file.exists():
            try:
                self.history = json.loads(self.history_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.history = []


def os_chmod_600(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
