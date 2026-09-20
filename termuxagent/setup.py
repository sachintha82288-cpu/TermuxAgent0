"""The first-run setup wizard — provider, key, model, tools, theme.

Everything is arrow-key menus + one-line questions, so a brand-new Termux
user can go from install to chatting in under a minute.
"""
from __future__ import annotations

import sys
from typing import List, Optional

from . import __version__, providers as prov
from .config import Config
from .llm import LLMError, list_models
from .theme import THEMES, box, paint, set_theme
from .ui import ask, ask_hidden, confirm, error, info, select, success, warn


def _provider_preview(idx_by_id):
    def preview(idx: int) -> List[str]:
        return []
    return preview


def _pick_provider(cfg: Config) -> Optional[dict]:
    """Flat provider chooser with group icons (every row is selectable)."""
    options: List[str] = []
    meta: List[dict] = []
    for icon, gid in (("☁", "cloud"), ("🖥", "local"), ("⚙", "custom")):
        for p in prov.by_group(gid):
            suffix = ""
            if p.get("needs_key") is False:
                suffix = " · no key"
            elif p.get("note"):
                suffix = f" · {p['note']}"
            options.append(f"{icon} {p['name']}{suffix}")
            meta.append(p)

    start = next((i for i, m in enumerate(meta) if m["id"] == cfg.provider_id), 0)
    idx = select("Choose your AI provider (27 supported)", options, index=start)
    if idx is None:
        return None
    return meta[idx]


def _can_open_url() -> bool:
    import shutil
    return bool(shutil.which("termux-open-url") or shutil.which("xdg-open")
                or shutil.which("open"))


def _open_url(url: str) -> None:
    import shutil
    import subprocess
    for cmd in ("termux-open-url", "xdg-open", "open"):
        if shutil.which(cmd):
            try:
                subprocess.Popen([cmd, url], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except OSError:
                pass
            return


def _enter_key(cfg: Config, p: dict) -> bool:
    if p.get("needs_key") is False:
        info(f"{p['name']} runs locally — no API key needed.")
        return True
    print()
    url = p.get("key_url") or ""
    print(box(
        [paint(f"Create a key at: {url or '(see provider docs)'}", "accent"),
         paint("(the key is hidden while you type — paste it and press Enter)", "muted")],
        title=p["name"] + " API key"))
    if url and _can_open_url():
        if confirm("Open that page in your browser?", default=False):
            _open_url(url)
    attempts = 0
    while attempts < 3:
        attempts += 1
        try:
            key = ask_hidden("Paste your API key" +
                             (f" (or set ${p['key_env']})" if p.get("key_env") else "") + ":")
        except (EOFError, KeyboardInterrupt):
            return False
        key = key.strip().strip("'\"")  # pasted with quotes / trailing space
        if not key:
            if confirm("Skip for now? (you can add it later with: agent setup)",
                       default=False):
                return False
            continue
        if " " in key or len(key) < 8:
            warn("that doesn't look like an API key — please paste it again.")
            continue
        cfg.set_key(p["id"], key)
        if cfg.base_url():
            from .ui import Spinner
            with Spinner(f"verifying key with {p['name']}"):
                try:
                    list_models(cfg.base_url(), key, headers=cfg.headers())
                    ok = True
                except LLMError as exc:
                    ok, err = False, str(exc)
            if ok:
                success(f"Key works ({cfg.masked_key()})")
                return True
            warn(f"The key was rejected: {err.splitlines()[0]}")
            if not confirm("Paste it again? (No = keep this key anyway)", default=True):
                return True
            continue
        success(f"key received: {cfg.masked_key()}")
        return True
    return False


def _pick_model(cfg: Config, p: dict, test_key: bool) -> str:
    fetched: List[str] = []
    if test_key and cfg.base_url():
        from .ui import Spinner
        with Spinner(f"testing connection → {p['name']}"):
            try:
                fetched = list_models(cfg.base_url(), cfg.api_key(),
                                      headers=cfg.headers())
            except LLMError:
                fetched = []
    if fetched:
        success(f"Connection OK — {len(fetched)} models available.")
    else:
        if test_key:
            warn("Could not fetch the model list (bad key or offline); using built-ins.")

    candidates = fetched or [m for m in p.get("models", [])]
    default_model = cfg.data["models"].get(p["id"]) or p.get("default_model") or ""
    if default_model and default_model not in candidates:
        candidates = [default_model] + candidates
    if not candidates:  # custom / LM Studio / llama.cpp with nothing loaded
        if p["id"] in ("lmstudio", "llamacpp"):
            info("no models reported by the server — load one there, or type "
                 "its name now (you can change it later with /model).")
        return ask("Model name", default_model)

    capped = candidates[:40]
    labels = [m + ("   (default)" if m == default_model else "") for m in capped]
    labels.append(paint("✎  type a model name manually…", "accent"))
    idx = select(f"Model for {p['name']}", labels,
                 index=capped.index(default_model) if default_model in capped else 0)
    if idx is None or idx == len(labels) - 1:
        return ask("Model name", default_model)
    return capped[idx]


def _pick_theme(cfg: Config) -> str:
    from .theme import banner

    def preview(idx: int) -> List[str]:
        name = list(THEMES)[idx]
        set_theme(name)
        return banner("AGENT", "", "")[:7] + [paint(f"theme: {name}", "muted")]

    names = list(THEMES)
    idx = select("Pick a theme (see live preview below)", names,
                 index=names.index(cfg.data.get("theme", "aurora")) if cfg.data.get("theme") in names else 0, preview=preview)
    chosen = names[idx] if idx is not None else cfg.data.get("theme", "aurora")
    set_theme(chosen)
    return chosen


def _quick_start_menu(cfg: Config) -> Optional[dict]:
    """First-run shortcut: recommended free providers up top, full list below."""
    quick = [("groq", "⚡ Groq — free tier · extremely fast · recommended"),
             ("gemini", "✨ Google Gemini — generous free tier (AI Studio key)"),
             ("openrouter", "🌐 OpenRouter — one key, hundreds of models"),
             ("ollama", "🖥 Ollama — runs on your device, no key needed")]
    labels = [lbl for _, lbl in quick] + [paint("… show all 27 providers", "muted")]
    idx = select("Choose a provider  (↑↓ · Enter)", labels, index=0,
                 allow_cancel=False)
    if idx is None:
        return None
    if idx == len(labels) - 1:
        return _pick_provider(cfg)
    return prov.get(quick[idx][0])


def run_setup(cfg: Config, first_run: bool = False) -> Config:
    """Interactive wizard.  Returns the (possibly saved) config."""
    from .theme import print_banner
    if first_run:
        print_banner(f"setup · v{__version__}")
        print()
        print(box([
            paint("Welcome! 👋  You'll be chatting in about a minute.", "primary", bold=True),
            "",
            "1. Choose an AI provider   (Groq = free and fast)",
            "2. Paste your API key      (we show you the link)",
            "3. Pick a model and a theme",
            "",
            paint("Nothing gets installed via pip or npm — just Python.", "muted"),
        ], title="setup", color="accent"))
        print()

    p = _quick_start_menu(cfg) if first_run else _pick_provider(cfg)
    if p is None:
        warn("Setup cancelled — nothing saved.")
        return cfg

    cfg.data["provider"] = p["id"]
    if p["id"] == "custom":
        while True:
            url = ask("Base URL (e.g. http://192.168.1.5:8080/v1)",
                      cfg.base_url()).strip().rstrip("/")
            if url.startswith(("http://", "https://")):
                break
            warn("the URL must start with http:// or https://")
        cfg.data["custom_base_urls"]["custom"] = url
    got_key = _enter_key(cfg, p)

    model = _pick_model(cfg, p, test_key=got_key or p.get("needs_key") is False)
    if model:
        cfg.set_model(p["id"], model)

    # tools
    if p.get("tools", True):
        cfg.data["tools"] = confirm("Enable agent tools? (shell + file access — "
                                    "that's what makes it a real agent)", default=True)
    else:
        cfg.data["tools"] = False
        info(f"{p['name']} doesn't support function calling — tools off "
             "(commands will be shown as ```run blocks you can execute).")

    cfg.data["theme"] = _pick_theme(cfg)

    path = cfg.save()
    print()
    print(box([
        paint(f"provider: {p['name']}", "primary", bold=True),
        f"model:    {cfg.model() or '(not set)'}",
        f"api key:  {cfg.masked_key() if got_key else '(skipped)'}",
        f"theme:    {cfg.data['theme']}",
        f"config:   {path}",
    ], title="saved", color="ok"))
    success("TermuxAgent ready! 🎉")
    print(paint("  Any time:  agent  ·  agent setup  ·  agent doctor", "muted"))
    print()
    if confirm("Start chatting now?", default=first_run):
        from .repl import run_repl
        run_repl(cfg)
    return cfg
