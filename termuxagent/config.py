"""Configuration storage — ``~/.termux-agent/config.json`` (chmod 600).

The file keeps per-provider API keys and model choices plus theme and agent
options.  Environment overrides: ``TERMUXAGENT_API_KEY``, ``TERMUXAGENT_MODEL``,
``TERMUXAGENT_PROVIDER``, ``TERMUXAGENT_HOME``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

from . import providers as prov

DEFAULTS: Dict = {
    "provider": "groq",
    "api_keys": {},            # provider id -> key
    "models": {},              # provider id -> model id
    "custom_base_urls": {},    # provider id -> url (for "custom")
    "theme": "neon",
    "tools": True,
    "auto_approve": False,
    "temperature": 0.6,
    "max_steps": 12,
    "shell_timeout": 120,
    "timeout": 90,
    "stream": True,
    "show_reasoning": True,
    "history": True,
    "system_extra": "",
}


LEGACY_HOME_NAME = ".termuxagent"     # pre-1.0.1 location (typo'd name)
HOME_NAME = ".termux-agent"           # matches install.sh / README / uninstall.sh


def storage_home() -> Path:
    """``~/.termux-agent`` (or ``$TERMUXAGENT_HOME``).

    Older versions stored everything in ``~/.termuxagent`` while the installer
    and docs used ``~/.termux-agent`` — so uninstall missed the config and the
    README pointed at a file that did not exist.  Migrate silently once.
    """
    custom = os.environ.get("TERMUXAGENT_HOME")
    if custom:
        return Path(custom).expanduser()
    home = Path.home() / HOME_NAME
    legacy = Path.home() / LEGACY_HOME_NAME
    if legacy.is_dir() and not (home / "config.json").exists():
        try:
            home.mkdir(parents=True, exist_ok=True)
            for name in ("config.json", "history.json", "last-session.json",
                         "input-history"):
                src = legacy / name
                if src.exists() and not (home / name).exists():
                    src.replace(home / name)
        except OSError:
            pass
    return home


def config_path() -> Path:
    return storage_home() / "config.json"


def history_path() -> Path:
    return storage_home() / "history.json"


def session_path() -> Path:
    return storage_home() / "last-session.json"


class Config:
    """Live configuration object with convenience accessors."""

    def __init__(self, data: Optional[Dict] = None) -> None:
        self.data: Dict = json.loads(json.dumps(DEFAULTS))
        if data:
            self.data.update({k: v for k, v in data.items() if k in DEFAULTS})

    # ------------------------------------------------------------- loading
    @classmethod
    def load(cls) -> "Config":
        raw: Dict = {}
        path = config_path()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
        cfg = cls(raw)
        cfg._apply_env()
        cfg._normalise()
        return cfg

    def _normalise(self) -> None:
        """Repair values a hand-edited config may have broken."""
        from .theme import THEMES
        if self.data.get("theme") not in THEMES:
            self.data["theme"] = DEFAULTS["theme"]
        for key in ("api_keys", "models", "custom_base_urls"):
            if not isinstance(self.data.get(key), dict):
                self.data[key] = {}
        for key in ("timeout", "shell_timeout", "max_steps"):
            try:
                self.data[key] = max(1, int(self.data[key]))
            except (TypeError, ValueError):
                self.data[key] = DEFAULTS[key]
        try:
            self.data["temperature"] = float(self.data["temperature"])
        except (TypeError, ValueError):
            self.data["temperature"] = DEFAULTS["temperature"]

    def _apply_env(self) -> None:
        """Environment overrides (never written back to disk)."""
        env_key = os.environ.get("TERMUXAGENT_API_KEY")
        env_model = os.environ.get("TERMUXAGENT_MODEL")
        env_provider = os.environ.get("TERMUXAGENT_PROVIDER")
        if env_provider and prov.get(env_provider):
            self.data["provider"] = env_provider
        if env_key:
            self.set_key(self.data["provider"], env_key)
        if env_model:
            self.set_model(self.data["provider"], env_model)

    def save(self) -> Path:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)  # contains API keys
        except OSError:
            pass
        return path

    # ------------------------------------------------------------- accessors
    def __getattr__(self, name: str):
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(name)

    @property
    def provider_id(self) -> str:
        pid = self.data["provider"]
        return pid if prov.get(pid) else "groq"

    @property
    def provider(self) -> Dict:
        return prov.get(self.provider_id) or prov.PROVIDERS[0]

    def base_url(self) -> str:
        p = self.provider
        if p["id"] == "custom":
            return (self.data["custom_base_urls"].get("custom") or "").rstrip("/")
        return p["base_url"]

    def api_key(self) -> str:
        pid = self.provider_id
        key = self.data["api_keys"].get(pid, "")
        if not key:
            env_name = self.provider.get("key_env", "")
            if env_name:
                key = os.environ.get(env_name, "")
        return key

    def headers(self) -> Dict[str, str]:
        """Extra HTTP headers for the active provider (static + key header)."""
        p = self.provider
        hdrs: Dict[str, str] = dict(p.get("headers") or {})
        key_header = p.get("key_header")
        if key_header and self.api_key():
            hdrs[key_header] = self.api_key()
        return hdrs

    def set_key(self, pid: str, key: str) -> None:
        if key:
            self.data["api_keys"][pid] = key

    def model(self) -> str:
        pid = self.provider_id
        model = self.data["models"].get(pid, "")
        if not model:
            model = self.provider.get("default_model", "")
        return model

    def set_model(self, pid: str, model: str) -> None:
        if model:
            self.data["models"][pid] = model

    def tools_enabled(self) -> bool:
        return bool(self.data["tools"]) and bool(self.provider.get("tools", True))

    def is_configured(self) -> bool:
        p = self.provider
        if p.get("needs_key") is False:
            return bool(self.base_url())
        if p["id"] == "custom":
            return bool(self.base_url())
        return bool(self.api_key() and self.base_url())

    def masked_key(self) -> str:
        key = self.api_key()
        if not key:
            return "(none)"
        if len(key) <= 10:
            return key[:2] + "***"
        return key[:5] + "…" + key[-4:]

    def summary(self) -> Dict:
        return {
            "provider": f"{self.provider['name']} ({self.provider_id})",
            "base_url": self.base_url() or "(not set)",
            "model": self.model() or "(not set)",
            "api_key": self.masked_key(),
            "theme": self.data["theme"],
            "tools": "on" if self.tools_enabled() else "off",
            "auto_approve": self.data["auto_approve"],
            "stream": self.data["stream"],
        }
