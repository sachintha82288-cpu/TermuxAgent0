"""
Tool implementations for TermuxAgent0.

Every tool returns a string that is fed back to the LLM as a tool message.
Tools are intentionally simple and safe-by-default.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Dict


# Whitelist of definitely dangerous commands/patterns the agent must confirm first.
DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf /*", "mkfs.", "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "> /dev/", "chmod -R 777 /",
]


def _truncate(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    return f"{head}\n...[truncated {len(text) - limit} chars]...\n{tail}"


def tool_shell(command: str, timeout: int = 10, working_dir: str | None = None) -> str:
    """Run a shell command and return its (stdout + stderr) output."""
    command = (command or "").strip()
    if not command:
        return "ERROR: empty command."

    for pat in DANGEROUS_PATTERNS:
        if pat in command:
            return (
                f"ERROR: command matches dangerous pattern '{pat}'. "
                "Refusing to run. Ask the user explicitly."
            )

    timeout = max(1, min(int(timeout), 120))
    cwd = working_dir or os.getcwd()
    try:
        proc = subprocess.run(
            ["sh", "-c", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s."
    except FileNotFoundError as e:
        return f"ERROR: {e}"

    out = proc.stdout or ""
    err = proc.stderr or ""
    joined = out
    if err:
        joined = (out + ("\n" if out else "") + "[stderr]\n" + err) if out else err
    if not joined.strip():
        joined = f"(command exited with code {proc.returncode}, no output)"
    return _truncate(joined)


def tool_read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"ERROR: file not found: {p}"
    if not p.is_file():
        return f"ERROR: not a regular file: {p}"
    try:
        return _truncate(p.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        return f"ERROR: {e}"


def tool_write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} chars to {p}"
    except OSError as e:
        return f"ERROR: {e}"


def tool_append_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"OK: appended to {p} (total size {p.stat().st_size} bytes)"
    except OSError as e:
        return f"ERROR: {e}"


def tool_ls(path: str = ".") -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"ERROR: path not found: {p}"
    try:
        entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = []
        for e in entries:
            prefix = "d " if e.is_dir() else "- "
            try:
                size = e.stat().st_size if e.is_file() else 0
                lines.append(f"{prefix}{e.name}/" if e.is_dir() else f"{prefix}{e.name} ({size} B)")
            except OSError:
                lines.append(f"? {e.name}")
        return "\n".join(lines) if lines else "(empty directory)"
    except OSError as e:
        return f"ERROR: {e}"


def tool_pwd() -> str:
    return os.getcwd()


def tool_set_var(name: str, value: str) -> str:
    # Session variables are kept by the app; this is just a safe no-op stub.
    os.environ[f"TA_VAR_{name}"] = value
    return f"OK: set ${name} for this session."


# Schema exposed to the LLM (OpenAI-style function calling).
TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run a shell command in Termux. Returns stdout + stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute."},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (1-120, default 10).",
                        "default": 10,
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory (default: current).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write/create a file, overwriting if it exists.",
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
            "name": "append_file",
            "description": "Append text to the end of a file.",
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
            "name": "ls",
            "description": "List the contents of a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default '.').", "default": "."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pwd",
            "description": "Print the current working directory.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_var",
            "description": "Store a named variable in the session environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["name", "value"],
            },
        },
    },
]


TOOL_DISPATCH: Dict[str, Callable[..., str]] = {
    "shell": tool_shell,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "append_file": tool_append_file,
    "ls": tool_ls,
    "pwd": tool_pwd,
    "set_var": tool_set_var,
}
