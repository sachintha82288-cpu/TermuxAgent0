"""Configuration storage — ``~/.termuxagent/config.json`` (chmod 600).

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


def storage_home() -> Path:
    custom = os.environ.get("TERMUXAGENT_HOME")
    return Path(custom).expanduser() if custom else Path.home() / ".termuxagent"


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
        return cfg

    def _apply_env(self) -> None:
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
