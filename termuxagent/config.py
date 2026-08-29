"""Configuration, storage paths and the first-run setup wizard.

Config is stored as JSON in ``~/.termuxagent/config.json`` (override with
``TERMUXAGENT_HOME``).  Environment variables always win over the file:

    TERMUXAGENT_API_KEY   TERMUXAGENT_BASE_URL   TERMUXAGENT_MODEL
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from . import __version__
from .ui import c, CYAN, GREEN, YELLOW, info, success, warn


PROVIDERS = {
    "groq": {
        "label": "Groq (free tier, very fast, recommended for Termux)",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "label": "OpenRouter (free + paid models)",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "openai": {
        "label": "OpenAI (paid)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "ollama": {
        "label": "Ollama (local, no API key — run `ollama serve`)",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3.1",
    },
    "custom": {
        "label": "Custom OpenAI-compatible endpoint",
        "base_url": "",
        "model": "",
    },
}


def storage_home() -> Path:
    """Directory used for config and conversation history."""
    custom = os.environ.get("TERMUXAGENT_HOME")
    root = Path(custom).expanduser() if custom else Path.home() / ".termuxagent"
    return root


def config_path() -> Path:
    return storage_home() / "config.json"


def history_path() -> Path:
    return storage_home() / "history.json"


@dataclass
class Config:
    api_key: str = ""
    base_url: str = "https://api.groq.com/openai/v1"
    model: str = "llama-3.3-70b-versatile"
    timeout: int = 60
    shell_timeout: int = 120
    auto_approve_shell: bool = False
    system_prompt_extra: str = ""
    tools_enabled: list = field(default_factory=lambda: ["shell", "read_file", "write_file", "edit_file", "list_dir"])

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        path = config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for key, value in data.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, value)
            except (json.JSONDecodeError, OSError) as exc:
                warn(f"Could not read config ({exc}); using defaults.")

        # Environment variables take precedence.
        env_key = os.environ.get("TERMUXAGENT_API_KEY")
        env_url = os.environ.get("TERMUXAGENT_BASE_URL")
        env_model = os.environ.get("TERMUXAGENT_MODEL")
        if env_key:
            cfg.api_key = env_key
        if env_url:
            cfg.base_url = env_url.rstrip("/")
        if env_model:
            cfg.model = env_model
        return cfg

    # ----------------------------------------------------------------- save
    def save(self) -> Path:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)  # the file holds an API key — keep it private
        except OSError:
            pass
        return path


# ---------------------------------------------------------------------- wizard
def _ask(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(c(prompt + suffix + ": ", CYAN)).strip()
        if value:
            return value
        if default is not None:
            return default


def _ask_secret(prompt: str, default: Optional[str] = None) -> str:
    import getpass

    suffix = f" [{default}]" if default else ""
    while True:
        value = getpass.getpass(c(prompt + suffix + ": ", CYAN)).strip()
        if value:
            return value
        if default is not None:
            return default


def setup_wizard(existing: Optional[Config] = None) -> Config:
    """Interactive first-run / reconfiguration wizard."""
    cfg = existing or Config()

    print()
    print(c(f"  TermuxAgent0 v{__version__} — setup", GREEN))
    print(c("  Answer the questions below; press Enter to accept [defaults].", ""))
    print()

    keys = list(PROVIDERS)
    for i, key in enumerate(keys, 1):
        print(f"   {c(str(i), YELLOW)}) {PROVIDERS[key]['label']}")
    while True:
        choice = _ask("Choose a provider (1-%d)" % len(keys), "1")
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            provider = keys[int(choice) - 1]
            break
        warn("Please enter a number from the list.")

    preset = PROVIDERS[provider]
    cfg.base_url = _ask("API base URL", preset["base_url"] or None)
    cfg.model = _ask("Model name", preset["model"] or None)
    if provider == "ollama":
        cfg.api_key = "not-needed"
    else:
        cfg.api_key = _ask_secret("API key (input hidden)", cfg.api_key or None)

    cfg.auto_approve_shell = _ask("Auto-approve shell commands? (yes/no)", "no").lower().startswith("y")

    path = cfg.save()
    success(f"Saved configuration to {path}")
    info(f"Model: {cfg.model}  •  Endpoint: {cfg.base_url}")
    print()
    return cfg


def is_configured(cfg: Config) -> bool:
    return bool(cfg.api_key and cfg.base_url and cfg.model)
