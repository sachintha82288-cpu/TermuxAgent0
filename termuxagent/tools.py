"""The agent's tools: shell commands plus basic file operations.

Every tool receives validated string arguments and returns a plain string
(or raises ToolError, which the agent loop turns into a tool result so the
model can recover).  ``TOOL_SPECS`` is the OpenAI-style JSON-schema list sent
to the model; ``TOOL_FUNCTIONS`` maps the tool name to its implementation.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional

from .config import Config


class ToolError(Exception):
    """Recoverable tool failure — the message is returned to the model."""


# --------------------------------------------------------------------- helpers
MAX_OUTPUT_CHARS = 12_000
MAX_READ_CHARS = 40_000


def _resolve(path_str: str, workdir: Path) -> Path:
    """Resolve a model-supplied path against the working directory."""
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = workdir / p
    # Collapse '..' so sandbox checks see the real target.
    return p.resolve()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    keep = limit // 2
    return (
        text[:keep]
        + f"\n... [truncated {len(text) - limit} chars] ...\n"
        + text[-keep:]
    )


# ---------------------------------------------------------------------- shell
def run_shell(command: str, cfg: Config, workdir: Path) -> str:
    if not command or not command.strip():
        raise ToolError("empty command")
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=cfg.shell_timeout,
            executable=os.environ.get("SHELL") or "/bin/sh",
        )
    except subprocess.TimeoutExpired:
        return f"[command timed out after {cfg.shell_timeout}s and was killed]"
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


# ---------------------------------------------------------------- file tools
def read_file(path: str, cfg: Config, workdir: Path) -> str:
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
        return text[:MAX_READ_CHARS] + f"\n... [truncated, file is {len(text)} chars] ..."
    return text


def write_file(path: str, content: str, cfg: Config, workdir: Path) -> str:
    p = _resolve(path, workdir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"cannot write {p}: {exc}") from exc
    action = "Overwrote" if existed else "Wrote"
    return f"{action} {p} ({len(content)} chars)."


def edit_file(path: str, old_text: str, new_text: str, cfg: Config, workdir: Path) -> str:
    p = _resolve(path, workdir)
    if not p.exists():
        raise ToolError(f"file not found: {p}")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"cannot read {p}: {exc}") from exc

    count = text.count(old_text)
    if count == 0:
        raise ToolError(
            "old_text not found in file. Use read_file to copy the exact text "
            "(including whitespace) before editing."
        )
    if count > 1:
        raise ToolError(
            f"old_text matches {count} places; it must be unique. "
            "Include more surrounding text to disambiguate."
        )
    try:
        p.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"cannot write {p}: {exc}") from exc
    return f"Edited {p}: replaced 1 occurrence."


def list_dir(path: str, cfg: Config, workdir: Path) -> str:
    p = _resolve(path or ".", workdir)
    if not p.exists():
        raise ToolError(f"path not found: {p}")
    if not p.is_dir():
        raise ToolError(f"{p} is not a directory")
    entries = []
    try:
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            marker = "/" if entry.is_dir() else ""
            try:
                size = entry.stat().st_size
                size_str = f" ({size} B)" if entry.is_file() else ""
            except OSError:
                size_str = ""
            entries.append(entry.name + marker + size_str)
    except OSError as exc:
        raise ToolError(f"cannot list {p}: {exc}") from exc
    if not entries:
        return f"{p} is empty."
    return "\n".join(entries)


# ------------------------------------------------------------------ registry
TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "shell": run_shell,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_dir": list_dir,
}

TOOL_SPECS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": (
                "Run a shell command (sh/bash on Termux/Linux) in the working "
                "directory and return stdout, stderr and exit code. Use for "
                "package installs (pkg/apt/pip), git, running scripts, "
                "inspecting the system, etc. Prefer the dedicated file tools "
                "for reading/writing files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path (relative to the working directory or absolute)."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or overwrite an existing one with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path."},
                    "content": {"type": "string", "description": "Full file content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace an exact, unique span of text in an existing file. "
                "Read the file first so old_text matches exactly, including "
                "indentation and newlines."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path."},
                    "old_text": {"type": "string", "description": "Exact text to find (must occur exactly once)."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the contents of a directory (dirs end with /).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path (default: working directory)."}},
                "required": [],
            },
        },
    },
]


def get_tool_specs(enabled: Optional[list] = None) -> List[dict]:
    if enabled is None:
        return TOOL_SPECS
    return [s for s in TOOL_SPECS if s["function"]["name"] in enabled]


def call_tool(name: str, arguments: dict, cfg: Config, workdir: Path) -> str:
    """Dispatch a tool call; always returns a string (never raises)."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"[error] unknown tool: {name}"

    kwargs = {"cfg": cfg, "workdir": workdir}
    if name == "shell":
        kwargs["command"] = str(arguments.get("command", ""))
    elif name == "read_file":
        kwargs["path"] = str(arguments.get("path", ""))
    elif name == "write_file":
        kwargs["path"] = str(arguments.get("path", ""))
        kwargs["content"] = str(arguments.get("content", ""))
    elif name == "edit_file":
        kwargs["path"] = str(arguments.get("path", ""))
        kwargs["old_text"] = str(arguments.get("old_text", ""))
        kwargs["new_text"] = str(arguments.get("new_text", ""))
    elif name == "list_dir":
        kwargs["path"] = str(arguments.get("path", "") or ".")

    try:
        return func(**kwargs)
    except ToolError as exc:
        return f"[error] {exc}"
    except Exception as exc:  # never let a tool crash the agent loop
        return f"[error] tool {name} failed: {exc}"
