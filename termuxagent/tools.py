"""The agent's tools: shell commands plus file operations.

``SPECS`` is the OpenAI function-tool schema list sent to the model;
``call_tool`` executes one call.  Shell and write tools ask the user for
approval first (via the ``approve`` callback in the agent loop), and a small
blocklist catches obviously catastrophic commands.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

MAX_OUTPUT_CHARS = 12_000
MAX_READ_CHARS = 40_000

# regexes (matched against the lower-cased, whitespace-normalised command)
# that are refused outright.  They are anchored to *command position* so that
# e.g. ``git commit -m "fix reboot bug"`` or ``grep shutdown log.txt`` pass.
_CMD_START = r"(?:^|[;&|(`]\s*|\$\(\s*|\bsudo\s+|\bexec\s+)"
DANGEROUS_PATTERNS = [
    (r"rm\s+(-\w*[rf]\w*\s+)+(/|/\*|~|\$home|\$prefix|/data)(\s|$)", "rm -rf /"),
    (r"mkfs(\.\w+)?\b", "mkfs"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"dd\s+.*of=/dev/", "dd to a device"),
    (r"chmod\s+(-\w*r\w*\s+)?[0-7]{3,4}\s+/(\s|$)", "chmod -R on /"),
    (r"chown\s+(-\w*r\w*\s+).*\s/(\s|$)", "chown -R on /"),
    (r"(shutdown|reboot|halt|poweroff)\b", "shutdown/reboot"),
    (r"init\s+[06]\b", "init 0/6"),
    (r"(termux-)?wipe(-data)?\b", "wipe"),
]
# patterns that are dangerous anywhere in the line (redirections)
_ANYWHERE_PATTERNS = [
    (r">\s*/dev/(sd[a-z]|mmcblk\d|block/|nvme\d)", "write to block device"),
]
DANGEROUS = ([re.compile(_CMD_START + pat) for pat, _ in DANGEROUS_PATTERNS] +
             [re.compile(pat) for pat, _ in _ANYWHERE_PATTERNS])
_DANGER_LABELS = [lbl for _, lbl in DANGEROUS_PATTERNS + _ANYWHERE_PATTERNS]


class ToolError(Exception):
    """Recoverable failure — message is returned to the model."""


# ------------------------------------------------------------------ schemas
SPECS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": (
                "Run a shell command in the user's Termux/Linux terminal and "
                "return stdout, stderr and the exit code. Use it for real "
                "actions: pkg/apt installs, git, python scripts, system info, "
                "termux-api commands (termux-battery-status, termux-notification, "
                "termux-toast, ...), network checks, anything on the device."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string",
                                "description": "The exact shell command to run"},
                    "timeout": {"type": "integer",
                                "description": "Max seconds to wait (default 120)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file (large files are truncated).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file (parent dirs created, "
                           "existing file backed up to <path>.bak).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace the first exact occurrence of old_text with "
                           "new_text in a file. Use read_file first to copy text "
                           "exactly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List a directory (name, type, size).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
        },
    },
]

TOOL_NAMES = [s["function"]["name"] for s in SPECS]
READ_ONLY = {"read_file", "list_dir"}


def specs(enabled: Optional[List[str]] = None) -> List[dict]:
    if enabled is None:
        return SPECS
    return [s for s in SPECS if s["function"]["name"] in enabled]


# ------------------------------------------------------------------ helpers
def summarize(name: str, args: Dict) -> str:
    if name == "shell":
        return str(args.get("command", "")).replace("\n", " ")[:120]
    if name in ("read_file", "list_dir"):
        return str(args.get("path", ""))
    if name == "write_file":
        return f"{args.get('path', '')} ({len(str(args.get('content', '')))} chars)"
    if name == "edit_file":
        return str(args.get("path", ""))
    return json.dumps(args)[:120]


def is_dangerous(command: str) -> Optional[str]:
    """Return a short label when *command* matches the blocklist, else None."""
    low = command.lower().replace("\n", " ; ")
    low = re.sub(r"\s+", " ", low).strip()
    for rx, label in zip(DANGEROUS, _DANGER_LABELS):
        if rx.search(low):
            return label
    return None


def _shell_executable() -> str:
    """A POSIX shell that understands ``-c``: the user's shell if it is one."""
    import shutil
    user_shell = os.environ.get("SHELL") or ""
    if os.path.basename(user_shell) in ("bash", "sh", "zsh", "dash", "ash", "ksh") \
            and os.access(user_shell, os.X_OK):
        return user_shell
    for name in ("bash", "sh"):
        found = shutil.which(name)
        if found:
            return found
    return "/bin/sh"


def _resolve(path_str: str, workdir: Path) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = workdir / p
    return p.resolve()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    keep = limit // 2
    return (text[:keep] +
            f"\n... [truncated {len(text) - limit} chars] ...\n" +
            text[-keep // 2:])


# ------------------------------------------------------------------ shell
def run_shell(command: str, timeout: int, workdir: Path) -> str:
    if not command or not command.strip():
        raise ToolError("empty command")
    bad = is_dangerous(command)
    if bad:
        raise ToolError(f"refused: command matches blocked pattern '{bad}'")
    try:
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive",
                   GIT_TERMINAL_PROMPT="0", PAGER="cat", GIT_PAGER="cat")
        proc = subprocess.run(
            command, shell=True, cwd=str(workdir), capture_output=True,
            text=True, errors="replace", stdin=subprocess.DEVNULL, env=env,
            timeout=max(5, min(timeout or 120, 600)),
            executable=_shell_executable())
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"")
        out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
        tail = ("\nOUTPUT SO FAR:\n" + _truncate(out.rstrip(), 2000)) if out.strip() else ""
        return (f"[command timed out after {exc.timeout:.0f}s and was killed — "
                f"it may have been waiting for input; use non-interactive flags "
                f"like -y]{tail}")
    except OSError as exc:
        raise ToolError(f"failed to start shell: {exc}") from exc

    parts = [f"(exit code {proc.returncode})"]
    if proc.stdout.strip():
        parts.append("STDOUT:\n" + _truncate(proc.stdout.rstrip()))
    if proc.stderr.strip():
        parts.append("STDERR:\n" + _truncate(proc.stderr.rstrip()))
    if not proc.stdout.strip() and not proc.stderr.strip():
        parts.append("(no output)")
    return "\n".join(parts)


# ------------------------------------------------------------------ files
def read_file(path: str, workdir: Path) -> str:
    p = _resolve(path, workdir)
    if not p.exists():
        raise ToolError(f"file not found: {p}")
    if p.is_dir():
        raise ToolError(f"{p} is a directory; use list_dir")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ToolError(f"cannot read {p}: {exc}") from exc
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + f"\n... [truncated, file is {len(text)} chars]"
    return text


def write_file(path: str, content: str, workdir: Path) -> str:
    p = _resolve(path, workdir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        if existed:  # keep a one-level backup before overwriting
            p.with_suffix(p.suffix + ".bak").write_text(
                p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        p.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"cannot write {p}: {exc}") from exc
    action = "Overwrote (backup saved)" if existed else "Wrote"
    return f"{action} {p} ({len(content)} chars)."


def edit_file(path: str, old_text: str, new_text: str, workdir: Path) -> str:
    p = _resolve(path, workdir)
    if not p.exists():
        raise ToolError(f"file not found: {p}")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ToolError(f"cannot read {p}: {exc}") from exc
    count = text.count(old_text)
    if count == 0:
        raise ToolError("old_text not found — read the file and copy it exactly")
    if count > 1:
        raise ToolError(f"old_text appears {count} times — include more context "
                        "so it is unique")
    p.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
    return f"Edited {p} (1 replacement)."


def list_dir(path: str, workdir: Path) -> str:
    p = _resolve(path, workdir)
    if not p.exists():
        raise ToolError(f"directory not found: {p}")
    if not p.is_dir():
        raise ToolError(f"{p} is a file; use read_file")
    try:
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except OSError as exc:
        raise ToolError(f"cannot list {p}: {exc}") from exc
    lines = []
    for e in entries[:200]:
        try:
            if e.is_dir():
                lines.append(f"[dir]  {e.name}/")
            else:
                lines.append(f"       {e.name}  ({e.stat().st_size} B)")
        except OSError:
            continue
    if not lines:
        return "(empty directory)"
    if len(entries) > 200:
        lines.append(f"... {len(entries) - 200} more entries")
    return "\n".join(lines)


# ------------------------------------------------------------------ dispatch
def call_tool(name: str, args: Dict, timeout: int, workdir: Path) -> str:
    """Execute one validated tool call → result string for the model."""
    if name == "shell":
        return run_shell(str(args.get("command", "")),
                         int(args.get("timeout") or timeout), workdir)
    if name == "read_file":
        return read_file(str(args.get("path", "")), workdir)
    if name == "write_file":
        return write_file(str(args.get("path", "")),
                          str(args.get("content", "")), workdir)
    if name == "edit_file":
        return edit_file(str(args.get("path", "")), str(args.get("old_text", "")),
                         str(args.get("new_text", "")), workdir)
    if name == "list_dir":
        return list_dir(str(args.get("path", "")), workdir)
    raise ToolError(f"unknown tool: {name}")
