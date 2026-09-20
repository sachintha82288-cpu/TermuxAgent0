"""Command dispatch — ``agent <command> [options] [prompt]``.

  agent                chat REPL           agent setup      configuration wizard
  agent ask "..."      one-shot question   agent providers  list 27 providers
  agent provider [id]  switch provider     agent models     list API models
  agent model  [name]  switch model        agent theme [n]  change theme
  agent doctor         diagnose setup      agent config     show config
  agent uninstall      remove everything
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__, providers as prov
from .config import Config, config_path, storage_home
from .llm import LLMError, list_models
from .theme import THEMES, box, paint, print_banner, set_theme
from .ui import Spinner, ask, confirm, error, info, select, success, warn, dim

COMMANDS = ("setup", "chat", "ask", "provider", "model", "theme", "providers",
            "models", "doctor", "config", "uninstall", "help", "version")

USAGE = """{p}TermuxAgent v{v}{r} — the AI agent that lives in your terminal

{p}usage{r}
  {a}agent{r}                       start chatting
  {a}agent ask{r} "do something"    one-shot: run the task, print answer, exit
  {a}agent setup{r}                 (re)configure provider · key · model · theme
  {a}agent provider{r} [id]         switch API provider
  {a}agent model{r} [name]          switch model
  {a}agent theme{r} [name]          switch theme ({themes}…)
  {a}agent providers{r}             list all 27 supported providers
  {a}agent models{r}                list models on the current provider
  {a}agent doctor{r}                diagnose your setup
  {a}agent config{r}                show config (key masked)
  {a}agent uninstall{r}             remove TermuxAgent

{p}options{r}
  {a}-y, --yes{r}       auto-approve tool actions (one-shot needs this)
  {a}-c, --continue{r}  resume the last conversation  (e.g. {a}agent -c{r})
  {a}-C, --chdir PATH{r}  work in this directory
  {a}-m, --model NAME{r}  override model for this run
  {a}-p, --provider ID{r} override provider for this run
  {a}--no-tools{r}      plain chat, no shell/file access
  {a}--version{r}       print version"""


def _usage() -> str:
    from .theme import colors_enabled
    themes = ", ".join(list(THEMES)[:5])
    if not colors_enabled():
        return USAGE.format(p="", a="", r="", v=__version__, themes=themes)
    return USAGE.format(p=paint("", "primary", bold=True),
                        a=paint("", "accent"), r="",
                        v=__version__, themes=themes)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["chat"]

    cmd = argv[0].lower()
    if cmd in ("-h", "--help", "help"):
        print(_usage())
        return 0
    if cmd in ("-v", "--version", "version"):
        print(f"TermuxAgent v{__version__}")
        return 0
    if cmd not in COMMANDS:
        if cmd.startswith("-"):
            # `agent -c` / `agent -y --no-tools` → flags only → open the chat
            argv = ["chat"] + argv
            cmd = "chat"
        else:
            # `agent "do something"` → treat as a one-shot ask
            argv = ["ask"] + argv
            cmd = "ask"

    flags, positional = _parse_flags(argv[1:])
    if flags["unknown"]:
        error(f"unknown option: {flags['unknown'][0]}  (see: agent help)")
        return 2
    if cmd == "chat" and positional:
        # `agent -y "do this"` → the text is a one-shot prompt
        cmd = "ask"
    cfg = Config.load()
    if flags["provider"]:
        if prov.get(flags["provider"]):
            cfg.data["provider"] = flags["provider"]
        else:
            error(f"unknown provider '{flags['provider']}' — see: agent providers")
            return 1
    if flags["model"]:
        cfg.set_model(cfg.provider_id, flags["model"])
    if flags["no_tools"]:
        cfg.data["tools"] = False
    set_theme(cfg.data["theme"])

    workdir = Path(flags["chdir"]).expanduser().resolve() if flags["chdir"] else Path.cwd()
    if not workdir.is_dir():
        error(f"not a directory: {workdir}")
        return 1

    if cmd == "setup":
        from .setup import run_setup
        try:
            run_setup(cfg, first_run=not cfg.is_configured())
        except (KeyboardInterrupt, EOFError):
            print()
            warn("setup cancelled.")
        return 0

    if cmd == "providers":
        return _show_providers()
    if cmd == "doctor":
        return _doctor(cfg)
    if cmd == "uninstall":
        return _uninstall()
    if cmd == "config":
        return _show_config(cfg)
    if cmd == "theme":
        return _theme_cmd(cfg, positional)
    if cmd == "provider":
        return _provider_cmd(cfg, positional)
    if cmd == "model":
        return _model_cmd(cfg, positional)
    if cmd == "models":
        return _models_cmd(cfg)

    # chat / ask — need a working configuration
    if not cfg.is_configured():
        info("පළවෙනි වතාව — AI provider එක connect කරමු (තත්පර 30යි).")
        print()
        from .setup import run_setup
        try:
            run_setup(cfg, first_run=True)
        except (KeyboardInterrupt, EOFError):
            print()
            error("setup cancelled — run 'agent setup' any time.")
            return 1
        return 0
    if cmd == "ask":
        if not positional:
            error('usage: agent ask "your question"')
            return 1
        return _one_shot(cfg, " ".join(positional), workdir,
                         yes=flags["yes"], resume=flags["continue"])
    _repl(cfg, workdir, resume=flags["continue"], yes=flags["yes"])
    return 0


# ------------------------------------------------------------------ flags
def _parse_flags(args):
    flags = {"yes": False, "continue": False, "no_tools": False, "chdir": "",
             "model": "", "provider": "", "unknown": []}
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":                      # everything after -- is the prompt
            positional.extend(args[i + 1:])
            break
        if a in ("-y", "--yes"):
            flags["yes"] = True
        elif a in ("-c", "--continue"):
            flags["continue"] = True
        elif a == "--no-tools":
            flags["no_tools"] = True
        elif a in ("-C", "--chdir"):
            i += 1
            flags["chdir"] = args[i] if i < len(args) else ""
        elif a in ("-m", "--model"):
            i += 1
            flags["model"] = args[i] if i < len(args) else ""
        elif a in ("-p", "--provider"):
            i += 1
            flags["provider"] = args[i] if i < len(args) else ""
        elif a.startswith("--") and len(a) > 2:
            flags["unknown"].append(a)
        else:
            positional.append(a)
        i += 1
    return flags, positional


# ------------------------------------------------------------------ commands
def _show_providers() -> int:
    print_banner(subtitle=f"{len(prov.PROVIDERS)} supported providers")
    print()
    for group, title in (("cloud", "☁  CLOUD PROVIDERS"), ("local", "🖥  LOCAL"),
                         ("custom", "⚙  CUSTOM")):
        print(paint(f"{title}", "primary", bold=True))
        for p in prov.by_group(group):
            key = "no key" if p.get("needs_key") is False else (
                "key" if p.get("key_url") else "key?")
            tools_txt, tools_col = (("tools", "ok") if p.get("tools")
                                    else ("no tools", "warn"))
            print(f"  {paint(p['id'].ljust(13), 'accent', bold=True)}"
                  f"{p['name'].ljust(30)}"
                  f"{paint(tools_txt.ljust(13), tools_col)}"
                  f"{paint(key, 'muted')}")
        print()
    dim("switch with:  agent provider <id>   (e.g. agent provider groq)")
    return 0


def _theme_cmd(cfg: Config, positional) -> int:
    from .theme import banner
    names = list(THEMES)
    arg = positional[0].lower() if positional else ""
    if arg and arg in THEMES:
        chosen = arg
    else:
        if arg:
            warn(f"unknown theme '{arg}' — pick one of: {', '.join(names)}")

        def preview(idx: int) -> list:
            set_theme(names[idx])
            return banner("AGENT", "", "")[:7] + [paint(f"theme: {names[idx]}", "muted")]

        idx = select("theme (live preview below)", names,
                     index=names.index(cfg.data["theme"]) if cfg.data["theme"] in names else 0, preview=preview)
        if idx is None:
            set_theme(cfg.data["theme"])
            return 0
        chosen = names[idx]
    cfg.data["theme"] = chosen
    cfg.save()
    set_theme(chosen)
    print_banner(subtitle=f"theme: {chosen}")
    success(f"theme → {chosen}")
    return 0


def _provider_cmd(cfg: Config, positional) -> int:
    from .setup import _pick_provider
    arg = positional[0].lower() if positional else ""
    if arg:
        p = prov.get(arg)
        if not p:
            error(f"unknown provider '{arg}' — run 'agent providers' for the list")
            return 1
    else:
        p = _pick_provider(cfg)
        if p is None:
            return 0
    cfg.data["provider"] = p["id"]
    if p["id"] == "custom" and not cfg.base_url():
        url = ask("Base URL (e.g. http://192.168.1.5:8080/v1)", "")
        cfg.data["custom_base_urls"]["custom"] = url.rstrip("/")
    if p.get("needs_key") is not False and not cfg.api_key():
        from .setup import _enter_key
        _enter_key(cfg, p)
    if not cfg.model():
        from .setup import _pick_model
        model = _pick_model(cfg, p, test_key=bool(cfg.api_key()))
        if model:
            cfg.set_model(p["id"], model)
    cfg.save()
    set_theme(cfg.data["theme"])
    print(box([f"provider: {p['name']}",
               f"model:    {cfg.model() or '(set with: agent model <name>)'}",
               f"api key:  {cfg.masked_key()}"],
              title="active", color="ok"))
    return 0


def _model_cmd(cfg: Config, positional) -> int:
    arg = positional[0] if positional else ""
    if arg:
        cfg.set_model(cfg.provider_id, arg)
        cfg.save()
        success(f"model → {arg}")
        return 0
    with Spinner(f"fetching models from {cfg.provider['name']}"):
        try:
            models = list_models(cfg.base_url(), cfg.api_key(),
                                 headers=cfg.headers())
        except LLMError as exc:
            models = []
            warn(str(exc))
    models = models or list(cfg.provider.get("models") or [])
    if not models:
        error("no model list available — set one manually: agent model <name>")
        return 1
    cur = cfg.model()
    idx0 = models.index(cur) if cur in models else 0
    idx = select("model", models[:40], index=idx0)
    if idx is not None:
        cfg.set_model(cfg.provider_id, models[idx])
        cfg.save()
        success(f"model → {models[idx]}")
    return 0


def _models_cmd(cfg: Config) -> int:
    with Spinner(f"asking {cfg.provider['name']} for its model list"):
        try:
            models = list_models(cfg.base_url(), cfg.api_key(),
                                 headers=cfg.headers())
        except LLMError as exc:
            error(str(exc))
            warn("check your key/base URL with: agent doctor")
            return 1
    print(paint(f"{cfg.provider['name']} — {len(models)} models", "primary", bold=True))
    cur = cfg.model()
    for m in models:
        mark = paint("❯", "accent", bold=True) if m == cur else " "
        print(f" {mark} {m}")
    dim("switch with:  agent model <name>")
    return 0


def _show_config(cfg: Config) -> int:
    print(box([f"{k:<12} {v}" for k, v in cfg.summary().items()],
              title=str(config_path()), color="primary"))
    dim("edit values:  agent setup   ·   config file: nano " + str(config_path()))
    return 0


def _doctor(cfg: Config) -> int:
    import platform
    import subprocess
    from .llm import ping
    set_theme(cfg.data["theme"])
    print_banner(subtitle="doctor")
    print()
    results = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        mark = paint("✓", "ok", bold=True) if ok else paint("✗", "error", bold=True)
        line = f" {mark} {name}" + (paint(f"  — {detail}", "muted") if detail else "")
        results.append((ok, line))

    py = sys.version_info
    check("python ≥ 3.8", py >= (3, 8), f"{py.major}.{py.minor}.{py.micro}")
    is_termux = "com.termux" in os.environ.get("PREFIX", "")
    check("termux environment", True,
          "Termux detected 🎉" if is_termux else
          f"not Termux ({platform.system()}) — agent still works")
    check("config file", config_path().exists(), str(config_path()))
    p = cfg.provider
    check("provider", bool(prov.get(cfg.provider_id)),
          f"{p['name']} ({cfg.provider_id})")
    if p.get("needs_key") is False or p["id"] == "custom":
        check("api key", True, "not required for this provider")
    else:
        check("api key", bool(cfg.api_key()),
              cfg.masked_key() if cfg.api_key() else
              f"missing — get one at {p.get('key_url', '?')} then: agent setup")
    check("model", bool(cfg.model()), cfg.model() or "(not set)")

    if cfg.base_url():
        with Spinner(f"pinging {p['name']}"):
            online = ping(cfg.base_url(), cfg.api_key(), headers=cfg.headers())
        check("API reachable", online,
              "connected ✓" if online else
              "no response — check internet / key / provider status")
    check("tools", True, "enabled" if cfg.tools_enabled() else "disabled (--no-tools)")
    if is_termux:
        check("termux-api", bool(shutil.which("termux-battery-status")),
              "installed" if shutil.which("termux-battery-status") else
              "optional — pkg install termux-api (toast, battery, sms…)")
        check("storage", (Path.home() / "storage").exists(),
              "termux-setup-storage" if not (Path.home() / "storage").exists() else
              "shared storage linked")

    for _, line in results:
        print(line)
    fails = sum(1 for ok, _ in results if not ok)
    print()
    if fails == 0:
        success("ඔක්කොම හරි ✓ — chat කරන්න:  agent")
        return 0
    warn(f"ප්‍රශ්න {fails}ක් හමුවුණා.")
    needs_setup = not cfg.api_key() and p.get("needs_key") is not False \
        and p["id"] != "custom"
    if needs_setup or not cfg.model():
        if confirm("දැන්ම setup wizard එකෙන් හදමුද?", default=True):
            from .setup import run_setup
            try:
                run_setup(cfg, first_run=False)
            except (KeyboardInterrupt, EOFError):
                print()
    else:
        dim("hint: agent setup  ·  agent provider <id>  ·  agent models")
    return 1


def _uninstall() -> int:
    home = storage_home()
    print(box([f"config+history: {home}",
               "launchers:       agent, Agent"],
              title="this removes", color="warn"))
    if not confirm("uninstall TermuxAgent?", default=False):
        info("cancelled.")
        return 0
    import shutil as _sh
    _sh.rmtree(home, ignore_errors=True)
    _sh.rmtree(Path.home() / ".termuxagent", ignore_errors=True)  # legacy dir
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    for d in (os.path.join(prefix, "bin"), os.path.expanduser("~/.local/bin"),
              os.path.expanduser("~/bin"), "/usr/local/bin"):
        for name in ("agent", "Agent"):
            try:
                os.remove(os.path.join(d, name))
            except OSError:
                pass
    success("TermuxAgent removed. (the cloned repo folder stays — delete it "
            "manually if you want)")
    return 0


# ------------------------------------------------------------------ chat
def _repl(cfg: Config, workdir: Path, resume: bool, yes: bool) -> None:
    from .repl import Repl
    try:
        Repl(cfg, resume=resume, yes=yes).run()
    except KeyboardInterrupt:
        print()


def _one_shot(cfg: Config, prompt: str, workdir: Path, yes: bool,
              resume: bool) -> int:
    from .agent import Agent
    from .history import load_history
    from .tools import summarize
    from .ui import error as _error

    def on_content(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def announce(name: str, args: dict) -> None:
        print("  " + paint("🔧", "accent") + " " +
              paint(name, "accent", bold=True) + " " +
              paint(summarize(name, args), "muted"))

    def approve(name: str, args: dict) -> bool:
        if yes:
            return True
        print(box([summarize(name, args)], title=f"approve {name}? (use -y to skip)",
                  color="warn"))
        return confirm("run it?", default=False)

    agent = Agent(cfg, workdir=workdir, on_content=on_content,
                  approve=approve, announce=announce)
    agent.new_session()
    if resume:
        old = load_history()
        if old:
            agent.load_messages(old)
    try:
        reply = agent.chat(prompt)
    except LLMError as exc:
        _error(str(exc))
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    print()
    if cfg.data["history"]:
        from .history import save_history
        try:
            save_history(agent.messages)
        except OSError:
            pass
    return 0 if "[error]" not in reply and "[stopped]" not in reply else 1
