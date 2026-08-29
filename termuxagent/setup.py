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


def _enter_key(cfg: Config, p: dict) -> bool:
    if p.get("needs_key") is False:
        info(f"{p['name']} runs locally — no API key needed.")
        return True
    print()
    print(box(
        [paint(f"Create a key at: {p.get('key_url') or '(see provider docs)'}", "accent")],
        title=p["name"] + " API key"))
    attempts = 0
    while attempts < 3:
        attempts += 1
        try:
            key = ask_hidden("Paste your API key" +
                             (f" (or set ${p['key_env']})" if p.get("key_env") else "") + ":")
        except (EOFError, KeyboardInterrupt):
            return False
        if not key:
            if confirm("Skip for now? (you can add it later with: agent setup)",
                       default=False):
                return False
            continue
        cfg.set_key(p["id"], key)
        return True
    return False


def _pick_model(cfg: Config, p: dict, test_key: bool) -> str:
    fetched: List[str] = []
    if test_key and cfg.base_url():
        from .ui import Spinner
        with Spinner(f"testing connection → {p['name']}"):
            try:
                fetched = list_models(cfg.base_url(), cfg.api_key(),
                                      headers=p.get("headers"))
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
    if p["id"] == "custom" and not candidates:
        return ask("Model name", "")

    capped = candidates[:40]
    labels = [m + ("   (default)" if m == default_model else "") for m in capped]
    labels.append(paint("✎  type a model name manually…", "accent"))
    idx = select(f"Model for {p['name']}", labels,
                 index=0 if default_model == capped[0] else 0)
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
                 index=names.index(cfg.data.get("theme", "neon")), preview=preview)
    chosen = names[idx] if idx is not None else cfg.data.get("theme", "neon")
    set_theme(chosen)
    return chosen


def run_setup(cfg: Config, first_run: bool = False) -> Config:
    """Interactive wizard.  Returns the (possibly saved) config."""
    from .theme import print_banner
    if first_run:
        print_banner(f"setup · v{__version__}")
        print()
        print(paint("Let's connect your agent to an AI. "
                    "Pick a provider — Groq has a fast free tier.", "muted"))
        print()

    p = _pick_provider(cfg)
    if p is None:
        warn("Setup cancelled — nothing saved.")
        return cfg

    if p["id"] == "custom":
        url = ask("Base URL (e.g. http://192.168.1.5:8080/v1)", cfg.base_url())
        cfg.data["custom_base_urls"]["custom"] = url.rstrip("/")

    cfg.data["provider"] = p["id"]
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
    success("TermuxAgent is ready.")
    print()
    if confirm("Start chatting now?", default=first_run):
        from .repl import run_repl
        run_repl(cfg)
    return cfg
