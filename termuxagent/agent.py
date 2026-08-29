"""The agentic loop: send messages → model asks for tools → run them → repeat."""
from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Callable, List, Optional

from . import __version__
from .config import Config
from .history import save_history
from .llm import LLMError, chat
from .tools import call_tool, get_tool_specs

MAX_ITERATIONS = 12

# Called with (tool_name, arguments_dict) when the model requests a tool.
# Return True to allow it, False to deny.  Default: allow everything.
ApprovalCallback = Callable[[str, dict], bool]
# Called with (tool_name, arguments_dict) just before a tool runs (for display).
AnnounceCallback = Callable[[str, dict], None]


def build_system_prompt(workdir: Path, cfg: Config) -> str:
    parts = [
        f"You are TermuxAgent0 v{__version__}, a helpful AI coding and shell "
        "assistant running inside a terminal on the user's own device.",
        f"Environment: {platform.system()} {platform.release()} on {platform.machine()}.",
        f"Working directory: {workdir}",
        "Shell: POSIX sh (on Termux use 'pkg' to install packages).",
        "",
        "How to work:",
        "- You have tools: shell, read_file, write_file, edit_file, list_dir.",
        "- Explore before acting: use list_dir/read_file to understand the "
        "context instead of guessing.",
        "- Take real action with the tools; verify results with shell or "
        "read_file afterwards.",
        "- Make changes in small, reversible steps. When a command or edit "
        "fails, read the error and adjust.",
        "- Shell commands that modify the system (installs, deletes, git push) "
        "may be shown to the user for approval.",
        "- Keep replies concise. Report what you did and any problems left.",
        "- Never ask for API keys, passwords or tokens; the environment is "
        "already configured.",
    ]
    if cfg.system_prompt_extra:
        parts.append("")
        parts.append(cfg.system_prompt_extra)
    return "\n".join(parts)


class Agent:
    def __init__(
        self,
        cfg: Config,
        workdir: Optional[Path] = None,
        on_content: Optional[Callable[[str], None]] = None,
        approve: Optional[ApprovalCallback] = None,
        announce: Optional[AnnounceCallback] = None,
    ) -> None:
        self.cfg = cfg
        self.workdir = (workdir or Path.cwd()).resolve()
        self.on_content = on_content
        self.approve = approve or (lambda name, args: True)
        self.announce = announce or (lambda name, args: None)
        self.messages: List[dict] = [
            {"role": "system", "content": build_system_prompt(self.workdir, cfg)}
        ]
        self.tools = get_tool_specs(cfg.tools_enabled)

    # ------------------------------------------------------------- history
    def load_history(self, messages: List[dict]) -> None:
        """Append prior conversation (list of role/content messages)."""
        self.messages.extend(messages)

    def persist(self) -> None:
        save_history(self.messages)

    def reset(self) -> None:
        self.messages = [self.messages[0]]  # keep system prompt

    # -------------------------------------------------------------- loop
    def chat(self, user_text: str) -> str:
        """Send *user_text* and run the tool loop; return final assistant text."""
        self.messages.append({"role": "user", "content": user_text})

        for _ in range(MAX_ITERATIONS):
            try:
                response = chat(
                    base_url=self.cfg.base_url,
                    api_key=self.cfg.api_key,
                    model=self.cfg.model,
                    messages=self.messages,
                    tools=self.tools,
                    timeout=self.cfg.timeout,
                    stream=True,
                    on_content=self.on_content,
                )
            except LLMError as exc:
                # Drop the pending user turn so the conversation stays usable.
                self.messages.pop()
                raise LLMError(str(exc)) from exc

            # Some providers stream content after tool calls; keep it tidy.
            if response.get("tool_calls") and response.get("content"):
                if self.on_content:
                    self.on_content("\n")
            if response.get("content") is None:
                response["content"] = ""

            if not response.get("tool_calls") and not response["content"].strip():
                # Drop the pending user turn so the conversation stays usable.
                self.messages.pop()
                raise LLMError("the model returned an empty response (connection problem or unsupported model?)")

            self.messages.append(response)
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                return response.get("content", "")

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                    result = f"[error] tool arguments were not valid JSON: {raw_args[:200]}"
                else:
                    self.announce(name, args)
                    if not self.approve(name, args):
                        result = "[denied by user]"
                    else:
                        result = call_tool(name, args, self.cfg, self.workdir)

                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "name": name,
                        "content": result,
                    }
                )

        return "[error] agent stopped after reaching the maximum number of tool steps."
