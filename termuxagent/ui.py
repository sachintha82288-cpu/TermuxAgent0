"""Tiny terminal colour helpers (disabled automatically when not on a TTY)."""
from __future__ import annotations

import os
import sys

_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _code(code: str) -> str:
    return f"\033[{code}m" if _ENABLED else ""


RESET = _code("0")
BOLD = _code("1")
DIM = _code("2")
RED = _code("31")
GREEN = _code("32")
YELLOW = _code("33")
BLUE = _code("34")
MAGENTA = _code("35")
CYAN = _code("36")


def c(text: str, color: str) -> str:
    """Colourise *text* (no-op when colours are disabled)."""
    return f"{color}{text}{RESET}" if _ENABLED else text


def info(msg: str) -> None:
    print(c("[*] ", CYAN) + msg)


def success(msg: str) -> None:
    print(c("[+] ", GREEN) + msg)


def warn(msg: str) -> None:
    print(c("[!] ", YELLOW) + msg)


def error(msg: str) -> None:
    print(c("[x] ", RED) + msg, file=sys.stderr)


def tool_call(name: str, summary: str) -> None:
    """Announce a tool invocation in dim text."""
    print(c(f"  . {name}: {summary}", DIM))
