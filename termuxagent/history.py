"""Conversation history persistence (survives between sessions)."""
from __future__ import annotations

import json
from typing import List

from .config import history_path
from .ui import warn


def load_history() -> List[dict]:
    path = history_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        warn(f"Could not read history ({exc}); starting fresh.")
    return []


def save_history(messages: List[dict]) -> None:
    """Persist the conversation (system message excluded)."""
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    convo = [m for m in messages if m.get("role") != "system"]
    path.write_text(json.dumps(convo, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_history() -> None:
    path = history_path()
    if path.exists():
        path.unlink()
