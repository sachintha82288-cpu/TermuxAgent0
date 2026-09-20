"""Interactive terminal UI toolkit (pure stdlib).

- ``select()``    arrow-key menu (j/k, digits, q to cancel) with live preview,
                  falls back to numbered input when stdin is not a TTY
- ``confirm()``   y/n question with a default
- ``Spinner``     ASCII spinner with elapsed time, disabled when piped
- message helpers themed through ``theme.py``
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable, List, Optional

from . import theme
from .theme import paint


# --------------------------------------------------------------------------
# message helpers
# --------------------------------------------------------------------------
def info(msg: str) -> None:
    print(paint("› ", "secondary", bold=True) + msg)


def success(msg: str) -> None:
    print(paint("✓ ", "ok", bold=True) + msg)


def warn(msg: str) -> None:
    print(paint("! ", "warn", bold=True) + msg)


def error(msg: str) -> None:
    print(paint("✗ ", "error", bold=True) + msg, file=sys.stderr)


def dim(msg: str) -> None:
    print(paint(msg, "muted"))


def clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


# --------------------------------------------------------------------------
# plain input helpers
# --------------------------------------------------------------------------
def ask(prompt: str, default: str = "") -> str:
    """Ask a free-text question; empty answer returns *default*."""
    suffix = f" {paint(f'[{default}]', 'muted')}" if default else " "
    try:
        raw = input(paint(prompt, "secondary", bold=True) + suffix).strip()
    except EOFError:
        return default
    return raw or default


def ask_hidden(prompt: str) -> str:
    """Read a secret without echoing it (getpass, plain fallback)."""
    import getpass
    try:
        return getpass.getpass(paint(prompt, "secondary", bold=True) + " ").strip()
    except EOFError:
        return ""


def confirm(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    try:
        raw = input(paint(f"? ", "warn", bold=True) + question +
                    " " + paint(f"[{hint}]", "muted") + " ").strip().lower()
    except EOFError:
        return default
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


# --------------------------------------------------------------------------
# raw key reading (arrow-key menus)
# --------------------------------------------------------------------------
def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _read_key() -> str:
    ch = sys.stdin.read(1)
    if ch == "":
        raise EOFError
    if ch != "\x1b":
        return ch
    import select as _select
    if not _select.select([sys.stdin], [], [], 0.05)[0]:
        return "ESC"
    nxt = sys.stdin.read(1)
    if nxt not in ("[", "O"):
        return "ESC"
    code = sys.stdin.read(1)
    if code.isdigit():                      # \x1b[1~ (home)  \x1b[4~ (end) …
        num = code
        while _select.select([sys.stdin], [], [], 0.05)[0]:
            c = sys.stdin.read(1)
            if c == "~" or not c.isdigit():
                break
            num += c
        return {"1": "HOME", "7": "HOME", "4": "END", "8": "END",
                "5": "PGUP", "6": "PGDN"}.get(num, "ESC")
    return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
            "H": "HOME", "F": "END"}.get(code, "ESC")


def select(title: str, options: List[str], index: int = 0,
           preview: Optional[Callable[[int], List[str]]] = None,
           allow_cancel: bool = True) -> Optional[int]:
    """Interactive single-choice menu.  Returns the chosen index or None."""
    if not options:
        return None

    try:
        import termios
        import tty
    except ImportError:  # Windows / exotic platforms → numbered menu
        termios = tty = None

    if not _interactive() or termios is None:  # numbered fallback for pipes / CI
        print(paint(title, "secondary", bold=True))
        for i, opt in enumerate(options, 1):
            marker = theme.paint(">", "accent", bold=True) if i - 1 == index else " "
            print(f"  {marker} {i}. {opt}")
        while True:
            try:
                raw = input(paint("choice", "secondary", bold=True) +
                            paint(f" [1-{len(options)}]", "muted") + " ").strip()
            except EOFError:
                return None
            if not raw:
                return index
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return int(raw) - 1
            if raw.lower() == "q":
                return None

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    visible = min(len(options), max(4, theme.term_height() - (8 if preview else 4)))
    top = 0
    cur = max(0, min(index, len(options) - 1))
    width = theme.term_width()
    last_lines: List[str] = []

    def render() -> List[str]:
        nonlocal top
        if cur < top:
            top = cur
        elif cur >= top + visible:
            top = cur - visible + 1
        lines = [paint(title, "secondary", bold=True)]
        if top > 0:
            lines.append(paint(f"  ↑ {top} more", "muted"))
        for i in range(top, min(len(options), top + visible)):
            opt = options[i]
            mark = paint("❯ ", "accent", bold=True) if i == cur else "  "
            name = theme.truncate(opt, max(8, width - 6))
            if i == cur:
                lines.append(mark + paint(name, "primary", bold=True))
            else:
                lines.append(mark + paint(name, "muted"))
        if top + visible < len(options):
            lines.append(paint(f"  ↓ {len(options) - top - visible} more", "muted"))
        if preview:
            lines.append("")
            lines.extend(preview(cur))
        if allow_cancel:
            lines.append(paint("  ↑↓ move · enter select · q cancel", "muted"))
        return lines

    try:
        tty.setcbreak(fd)
        sys.stdout.write("\033[?25l")  # hide cursor
        lines = render()
        for ln in lines:
            sys.stdout.write("\r\033[2K" + ln + "\n")
        sys.stdout.flush()
        last_lines = lines

        while True:
            key = _read_key()
            if key in ("UP", "k"):
                cur = (cur - 1) % len(options)
            elif key in ("DOWN", "j"):
                cur = (cur + 1) % len(options)
            elif key in ("HOME", "g"):
                cur = 0
            elif key in ("END", "G"):
                cur = len(options) - 1
            elif key == "PGUP":
                cur = max(0, cur - visible)
            elif key == "PGDN":
                cur = min(len(options) - 1, cur + visible)
            elif key.isdigit() and 1 <= int(key) <= min(9, len(options)):
                cur = int(key) - 1
            elif key in ("\r", "\n", " ", "RIGHT"):
                return cur
            elif key in ("q", "ESC") and allow_cancel:
                return None
            elif key == "\x03":
                raise KeyboardInterrupt
            else:
                continue

            # redraw in place
            sys.stdout.write(f"\033[{len(last_lines)}F")
            lines = render()
            for ln in lines:
                sys.stdout.write("\r\033[2K" + ln + "\n")
            if len(lines) < len(last_lines):
                sys.stdout.write("\033[J")
            sys.stdout.flush()
            last_lines = lines
    except (KeyboardInterrupt, EOFError):
        return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass
        sys.stdout.write("\033[?25h")  # show cursor
        sys.stdout.flush()
    return None


# --------------------------------------------------------------------------
# spinner
# --------------------------------------------------------------------------
class Spinner:
    """A tiny animated spinner; a silent no-op when stdout is not a TTY.

    Usable as a context manager or manually: ``sp.start()`` … ``sp.stop()``.
    """

    FRAMES = "|/-\\"

    def __init__(self, label: str = "working"):
        self.label = label
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = sys.stdout.isatty()
        self._running = False

    def _spin(self) -> None:
        start = time.time()
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            elapsed = int(time.time() - start)
            sys.stdout.write(
                "\r\033[2K" + paint(f" {frame} ", "accent", bold=True) +
                paint(self.label, "muted") + paint(f"  {elapsed}s", "muted"))
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.1)

    def start(self) -> "Spinner":
        if self._running:
            return self
        self._running = True
        self._stop.clear()
        if self._active:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop.set()
        if self._active and self._thread:
            self._thread.join(timeout=1)
            sys.stdout.write("\r\033[2K\033[?25h")
            sys.stdout.flush()

    def __enter__(self) -> "Spinner":
        if self._active:
            self.start()
        else:
            print(paint(f"… {self.label}", "muted"))
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def truncate_text(text: str, limit: int = 3000) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 4:]
    return f"{head}\n... [truncated {len(text) - limit} chars] ...\n{tail}"
