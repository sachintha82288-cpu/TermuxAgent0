"""Theme engine — colours, gradients, banners and boxes.

12 built-in themes, each defining a palette of 256-colour codes.  The banner
renderer joins big block letters and paints each row with a colour
interpolated between the theme's gradient stops, so every theme gets its own
look.  All styling is a no-op when colours are disabled (``NO_COLOR``, pipe,
or the ``mono`` theme).
"""
from __future__ import annotations

import os
import shutil
import sys
from typing import Dict, List, Optional

# --------------------------------------------------------------------------
# palettes (xterm-256 colour codes)
# --------------------------------------------------------------------------
THEMES: Dict[str, Dict[str, str]] = {
    # ── the flagship theme: 24-bit aurora gradient (violet → cyan → mint),
    #    falls back to the nearest 256-colours on older terminals
    "aurora": {
        "primary": "141", "secondary": "80", "accent": "86",
        "muted": "245", "error": "204", "warn": "221", "ok": "121",
        "grad_a": "99", "grad_b": "80", "grad_c": "121",
        "rgb": {"primary": "b48cff", "secondary": "4fd6ff", "accent": "5cf5c8",
                "muted": "8b8fa3", "error": "ff6b8a", "warn": "ffd166", "ok": "6ef3a5",
                "grad_a": "8a5cff", "grad_b": "3ad7ff", "grad_c": "5cf5a0"},
    },
    "neon": {
        "primary": "201", "secondary": "51", "accent": "46",
        "muted": "245", "error": "196", "warn": "220", "ok": "46",
        "grad_a": "201", "grad_b": "51", "grad_c": "46",
    },
    "cyberpunk": {
        "primary": "213", "secondary": "207", "accent": "220",
        "muted": "245", "error": "196", "warn": "220", "ok": "84",
        "grad_a": "129", "grad_b": "207", "grad_c": "213",
    },
    "matrix": {
        "primary": "46", "secondary": "40", "accent": "48",
        "muted": "238", "error": "196", "warn": "220", "ok": "46",
        "grad_a": "22", "grad_b": "40", "grad_c": "48",
    },
    "dracula": {
        "primary": "141", "secondary": "81", "accent": "213",
        "muted": "245", "error": "203", "warn": "220", "ok": "84",
        "grad_a": "99", "grad_b": "141", "grad_c": "213",
    },
    "nord": {
        "primary": "111", "secondary": "110", "accent": "140",
        "muted": "245", "error": "174", "warn": "179", "ok": "108",
        "grad_a": "74", "grad_b": "111", "grad_c": "140",
    },
    "sunset": {
        "primary": "209", "secondary": "204", "accent": "220",
        "muted": "245", "error": "196", "warn": "220", "ok": "215",
        "grad_a": "202", "grad_b": "209", "grad_c": "213",
    },
    "ocean": {
        "primary": "39", "secondary": "50", "accent": "81",
        "muted": "245", "error": "196", "warn": "220", "ok": "50",
        "grad_a": "24", "grad_b": "39", "grad_c": "50",
    },
    "sakura": {
        "primary": "218", "secondary": "175", "accent": "223",
        "muted": "245", "error": "204", "warn": "216", "ok": "150",
        "grad_a": "175", "grad_b": "218", "grad_c": "223",
    },
    "ruby": {
        "primary": "196", "secondary": "160", "accent": "214",
        "muted": "245", "error": "196", "warn": "220", "ok": "114",
        "grad_a": "52", "grad_b": "160", "grad_c": "196",
    },
    "gold": {
        "primary": "220", "secondary": "214", "accent": "178",
        "muted": "245", "error": "196", "warn": "220", "ok": "114",
        "grad_a": "172", "grad_b": "214", "grad_c": "220",
    },
    "vaporwave": {
        "primary": "219", "secondary": "51", "accent": "213",
        "muted": "245", "error": "196", "warn": "222", "ok": "50",
        "grad_a": "171", "grad_b": "213", "grad_c": "51",
    },
    "mono": {
        "primary": "252", "secondary": "250", "accent": "245",
        "muted": "242", "error": "248", "warn": "248", "ok": "248",
        "grad_a": "238", "grad_b": "245", "grad_c": "252",
    },
}

DEFAULT_THEME = "aurora"
_current = dict(THEMES[DEFAULT_THEME])
_colors_enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _detect_truecolor() -> bool:
    if os.environ.get("TERMUXAGENT_TRUECOLOR") in ("0", "false"):
        return False
    ct = os.environ.get("COLORTERM", "").lower()
    if ct in ("truecolor", "24bit"):
        return True
    term = os.environ.get("TERM", "")
    # Termux's terminal supports 24-bit even though COLORTERM is often unset
    return "com.termux" in os.environ.get("PREFIX", "") or "direct" in term


_truecolor = _detect_truecolor()


def truecolor_enabled() -> bool:
    return _truecolor


def _hex_to_rgb(hx: str):
    hx = hx.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


def _fg(role: str) -> str:
    """ANSI foreground sequence for a palette role (24-bit when possible)."""
    rgb = _current.get("rgb") if isinstance(_current.get("rgb"), dict) else None
    if _truecolor and rgb and role in rgb:
        r, g, b = _hex_to_rgb(rgb[role])
        return f"\033[38;2;{r};{g};{b}m"
    return f"\033[38;5;{color_of(role)}m"


# --------------------------------------------------------------------------
# core helpers
# --------------------------------------------------------------------------
def set_theme(name: str) -> None:
    """Activate a theme by name (unknown names fall back to *aurora*)."""
    global _current
    _current = dict(THEMES.get(name, THEMES[DEFAULT_THEME]))


def get_theme_name() -> str:
    for name, palette in THEMES.items():
        if palette == _current:
            return name
    return DEFAULT_THEME


def colors_enabled() -> bool:
    return _colors_enabled


def enable_colors(enabled: bool) -> None:
    global _colors_enabled
    _colors_enabled = enabled


def color_of(role: str) -> str:
    """The 256-colour code for a palette role."""
    return _current.get(role, "250")


def paint(text: str, role: str = "primary", *, bold: bool = False,
          dim: bool = False, italic: bool = False) -> str:
    """Colourise *text* with the active theme (no-op when disabled)."""
    if not _colors_enabled:
        return text
    prefix = ""
    if bold:
        prefix += "\033[1m"
    if dim:
        prefix += "\033[2m"
    if italic:
        prefix += "\033[3m"
    prefix += _fg(role)
    return f"{prefix}{text}\033[0m"


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _gradient(text: str, t: float) -> str:
    """Paint *text* at position *t* (0..1) along the 3-stop gradient."""
    if not _colors_enabled:
        return text
    rgb = _current.get("rgb") if isinstance(_current.get("rgb"), dict) else None
    if _truecolor and rgb and all(k in rgb for k in ("grad_a", "grad_b", "grad_c")):
        a, b, c = (_hex_to_rgb(rgb["grad_a"]), _hex_to_rgb(rgb["grad_b"]),
                   _hex_to_rgb(rgb["grad_c"]))
        if t <= 0.5:
            lo, hi, k = a, b, t * 2
        else:
            lo, hi, k = b, c, (t - 0.5) * 2
        r, g, bl = (_lerp(lo[i], hi[i], k) for i in range(3))
        return f"\033[38;2;{r};{g};{bl}m{text}\033[0m"
    a, b, c = (int(_current["grad_a"]), int(_current["grad_b"]), int(_current["grad_c"]))
    if t <= 0.5:
        lo, hi, k = a, b, t * 2
    else:
        lo, hi, k = b, c, (t - 0.5) * 2
    code = _lerp(lo, hi, k)
    return f"\033[38;5;{code}m{text}\033[0m"


# --------------------------------------------------------------------------
# box drawing
# --------------------------------------------------------------------------
def term_width() -> int:
    try:
        return shutil.get_terminal_size(fallback=(58, 24)).columns
    except Exception:  # pragma: no cover
        return 58


def term_height() -> int:
    try:
        return shutil.get_terminal_size(fallback=(58, 24)).lines
    except Exception:  # pragma: no cover
        return 24


_ANSI_RE = None


def strip_ansi(text: str) -> str:
    global _ANSI_RE
    if _ANSI_RE is None:
        import re
        _ANSI_RE = re.compile(r"\033\[[0-9;]*m")
    return _ANSI_RE.sub("", text)


def char_width(ch: str) -> int:
    """Terminal cell width of one character (0 for combining marks such as
    Sinhala vowel signs, 2 for wide CJK/emoji, else 1)."""
    import unicodedata
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    o = ord(ch)
    if 0x1F300 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF and o in _WIDE_SYMBOLS:
        return 2
    return 1


# common symbols/emoji that terminals render 2 cells wide
_WIDE_SYMBOLS = {0x2705, 0x274C, 0x2728, 0x26A1, 0x2B50, 0x2614, 0x2615}


def visible_len(text: str) -> int:
    """Display width of *text* ignoring ANSI escapes (Unicode-aware)."""
    return sum(char_width(ch) for ch in strip_ansi(text))


def truncate(text: str, width: int) -> str:
    """Cut *text* to *width* cells, keeping ANSI styling intact."""
    if visible_len(text) <= width:
        return text
    out, used, i = [], 0, 0
    limit = max(1, width - 1)
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            if j != -1:
                out.append(text[i:j + 1])
                i = j + 1
                continue
        w = char_width(text[i])
        if used + w > limit:
            break
        out.append(text[i])
        used += w
        i += 1
    return "".join(out) + "\033[0m~" if "\033" in text else "".join(out) + "~"


def box(lines: List[str], *, title: str = "", color: str = "primary",
        style: str = "round", width: Optional[int] = None) -> str:
    """Render a themed box around *lines* (already-coloured text is fine)."""
    tl, tr, bl, br, h, v = {
        "round": ("╭", "╮", "╰", "╯", "─", "│"),
        "heavy": ("┏", "┓", "┗", "┛", "━", "┃"),
    }[style]
    inner = (width or min(term_width() - 2, 64)) - 2
    lines = [truncate(ln, inner) for ln in lines]
    longest = max([visible_len(ln) for ln in lines] + [visible_len(title)]) or 1

    def bar(side_l: str, side_r: str, label: str = "") -> str:
        if label:
            middle = f" {label} "
            pad = longest + 2 - visible_len(middle)
            return paint(side_l + h + middle + h * max(1, pad) + side_r, color)
        return paint(side_l + h * (longest + 2) + side_r, color)

    out = [bar(tl, tr, title)]
    for ln in lines:
        gap = " " * max(0, longest - visible_len(ln))
        out.append(paint(v, color) + " " + ln + gap + " " + paint(v, color))
    out.append(bar(bl, br))
    return "\n".join(out)


def rule(label: str = "", color: str = "muted", char: str = "─") -> str:
    width = max(term_width(), 24)
    if label:
        seg = max(3, (width - visible_len(label) - 2) // 2)
        text = char * seg + f" {label} " + char * seg
        return paint(text[:width], color)
    return paint(char * width, color)


# --------------------------------------------------------------------------
# big banner (ANSI-shadow block letters, joined dynamically)
# --------------------------------------------------------------------------
_LETTERS: Dict[str, List[str]] = {
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "B": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██████╔╝", "╚═════╝ "],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "G": [" ██████╗ ", "██╔════╝ ", "██║  ███╗", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "M": ["███╗   ███╗", "████╗ ████║", "██╔████╔██║", "██║╚██╔╝██║", "██║ ╚═╝ ██║", "╚═╝     ╚═╝"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "U": ["██╗   ██╗", "██║   ██║", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "X": ["██╗  ██╗", "╚██╗██╔╝", " ╚███╔╝ ", " ██╔██╗ ", "██╔╝ ██╗", "╚═╝  ╚═╝"],
    "Y": ["██╗   ██╗", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚██╔╝  ", "   ██║   ", "   ╚═╝   "],
    " ": ["   "] * 6,
}


def _big_text(word: str) -> List[str]:
    word = word.upper()
    rows = [""] * 6
    for ch in word:
        glyph = _LETTERS.get(ch)
        if glyph is None:  # unknown glyph — fall back to a plain char
            glyph = [ch.center(3)] * 6
        rows = [r + g + " " for r, g in zip(rows, glyph)]
    return rows


def banner(word_a: str = "TERMUX", word_b: str = "AGENT",
           subtitle: str = "") -> List[str]:
    """The startup banner as a list of coloured lines (gradient by row)."""
    big = _big_text(word_a) + [""] + _big_text(word_b) if word_b else _big_text(word_a)
    needed = max(len(r.rstrip()) for r in big) + 4
    width = term_width()
    if width < needed:  # narrow phone screen → compact one-liner
        title = f"◆ {word_a} {word_b} ◆".replace("  ", " ")
        line1 = "\033[1m" + gradient_text(title) + "\033[0m" if _colors_enabled else title
        line2 = paint("─" * min(width - 2, len(title)), "muted")
        return [line1, line2] + ([paint(subtitle, "muted")] if subtitle else [])

    lines = [_gradient(row, i / max(1, len(big) - 1)) for i, row in enumerate(big)]
    if subtitle:
        lines.append("")
        lines.append(paint(subtitle.center(needed)[: width - 2], "accent"))
    return lines


def gradient_text(text: str) -> str:
    """Paint each character of *text* along the gradient (left → right)."""
    if not _colors_enabled or not text:
        return text
    n = max(1, len(text) - 1)
    return "".join(_gradient(ch, i / n) for i, ch in enumerate(text)).replace(
        "\033[0m\033[38", "\033[38")


def print_banner(subtitle: str = "") -> None:
    for line in banner(subtitle=subtitle):
        print(line)
