"""The agentic loop: user → model → tool calls → results → repeat."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from . import __version__
from .config import Config
from .llm import LLMError, chat
from .tools import READ_ONLY, ToolError, call_tool, specs, summarize

MAX_ITERATIONS = 12

# approve(name, args) → bool ; announce(name, args, result=None)
ApproveFn = Callable[[str, dict], bool]
AnnounceFn = Callable[[str, dict], None]


def _env_block() -> str:
    is_termux = "com.termux" in os.environ.get("PREFIX", "")
    shell = os.environ.get("SHELL") or "sh"
    try:
        kernel = subprocess.run(["uname", "-o", "-r"], capture_output=True,
                                text=True, timeout=5).stdout.strip()
    except Exception:
        kernel = f"{platform.system()} {platform.release()}"
    lines = [
        f"- device: {kernel or platform.platform()}",
        f"- termux: {'yes' if is_termux else 'no'}",
        f"- shell: {shell}   python: {platform.python_version()}",
        f"- termux-api CLI: "
        + ("installed" if shutil.which("termux-battery-status") else
           "not installed (suggest 'pkg install termux-api' when needed)"),
    ]
    return "\n".join(lines)


def build_system_prompt(cfg: Config, workdir: Path, tools_on: bool) -> str:
    parts = [
        f"You are TermuxAgent v{__version__} — a REAL AI agent running inside "
        f"the user's terminal. You don't just talk: you use tools to actually "
        f"do things on the device.",
        "",
        "ENVIRONMENT",
        _env_block(),
        f"- working directory: {workdir}",
        "",
        "HOW TO WORK",
        "- If the request can be done on this device, DO it with tools instead "
        "of only explaining.",
        "- Explore first (list_dir/read_file) when files are involved; then act; "
        "then verify the result.",
        "- On Termux install packages with 'pkg install -y <name>'.",
        "- Destructive or risky actions are shown to the user for approval — "
        "that's automatic, just proceed.",
        "- When a command fails, read the error and adapt (install a missing "
        "dependency, fix the path, ...) before giving up.",
        "- Keep answers short and terminal-friendly: plain text, short bullets. "
        "No giant tables. Reply in the user's language (Sinhala → Sinhala).",
        "- Never pretend you ran something you didn't; tool output is the truth.",
        "- Never ask the user for their API key or passwords.",
    ]
    if tools_on:
        parts.append("- Tools available: shell, read_file, write_file, "
                     "edit_file, list_dir.")
    else:
        parts.append(
            "- You have NO tool access in this session. When something should "
            "be run on the device, put the command in a ```run code fence — "
            "the terminal will offer to execute it.")
    if cfg.data.get("system_extra"):
        parts += ["", "USER INSTRUCTIONS", cfg.data["system_extra"]]
    return "\n".join(parts)


class Agent:
    """One conversation: system prompt + messages + the tool loop."""

    def __init__(self, cfg: Config, workdir: Optional[Path] = None,
                 on_content: Optional[Callable[[str], None]] = None,
                 on_reasoning: Optional[Callable[[str], None]] = None,
                 approve: Optional[ApproveFn] = None,
                 announce: Optional[AnnounceFn] = None,
                 tools_on: Optional[bool] = None) -> None:
        self.cfg = cfg
        self.workdir = (workdir or Path.cwd()).resolve()
        self.on_content = on_content
        self.on_reasoning = on_reasoning
        self.approve = approve or (lambda name, args: True)
        self.announce = announce or (lambda name, args: None)
        self.tools_on = cfg.tools_enabled() if tools_on is None else tools_on
        self.usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
        self.messages: List[dict] = []

    def new_session(self) -> None:
        self.messages = [{
            "role": "system",
            "content": build_system_prompt(self.cfg, self.workdir, self.tools_on),
        }]

    def load_messages(self, messages: List[dict]) -> None:
        self.new_session()
        for m in messages:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                self.messages.append({"role": m["role"], "content": m["content"]})

    # ------------------------------------------------------------------ core
    def _call_llm(self) -> dict:
        return chat(
            base_url=self.cfg.base_url(),
            api_key=self.cfg.api_key(),
            model=self.cfg.model(),
            messages=self.messages,
            tools=specs() if self.tools_on else None,
            timeout=self.cfg.data["timeout"],
            stream=self.cfg.data["stream"],
            temperature=self.cfg.data["temperature"],
            extra_headers=self.cfg.headers(),
            on_content=self.on_content,
            on_reasoning=self.on_reasoning if self.cfg.data["show_reasoning"] else None,
        )

    def chat(self, user_text: str) -> str:
        """One user turn → run the tool loop → final assistant text."""
        mark = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})
        try:
            return self._loop()
        except LLMError:
            # drop the whole failed turn (user msg + any partial tool steps)
            # so the next request is not rejected for a dangling tool_call
            del self.messages[mark:]
            raise
        except KeyboardInterrupt:
            self._repair_after_interrupt(mark)
            raise

    def _repair_after_interrupt(self, mark: int) -> None:
        """Ctrl+C mid-turn: keep what happened but leave a valid transcript.

        An assistant message with tool_calls must be followed by one tool
        result per call, otherwise every provider rejects the next request.
        """
        if len(self.messages) <= mark + 1:
            return
        last = self.messages[-1]
        if last.get("role") == "assistant" and last.get("tool_calls"):
            for call in last["tool_calls"]:
                self.messages.append({"role": "tool",
                                      "tool_call_id": call.get("id", ""),
                                      "name": call.get("function", {}).get("name", ""),
                                      "content": "[interrupted by user]"})
        elif last.get("role") == "tool":
            # fill in results for any calls of the preceding assistant msg
            for i in range(len(self.messages) - 1, mark, -1):
                m = self.messages[i]
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    done = {t.get("tool_call_id") for t in self.messages[i + 1:]}
                    for call in m["tool_calls"]:
                        if call.get("id", "") not in done:
                            self.messages.append({
                                "role": "tool", "tool_call_id": call.get("id", ""),
                                "name": call.get("function", {}).get("name", ""),
                                "content": "[interrupted by user]"})
                    break

    def _loop(self) -> str:
        max_steps = int(self.cfg.data.get("max_steps") or MAX_ITERATIONS)
        for _ in range(max_steps):
            response = self._call_llm()
            self._track_usage()
            if response.get("content") is None:
                response["content"] = ""
            if not response.get("tool_calls") and not response["content"].strip():
                raise LLMError("the model returned an empty response "
                               "(connection problem or unsupported model?)")
            self.messages.append(response)
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                return response.get("content", "")
            for call in tool_calls:
                self._run_one_tool(call)
        return ("[stopped] the agent hit the maximum number of tool steps "
                f"({max_steps}) for one request — say 'continue' to keep going.")

    def _run_one_tool(self, call: dict) -> None:
        fn = call.get("function", {})
        name = fn.get("name", "")
        raw = fn.get("arguments", "") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
        except (json.JSONDecodeError, ValueError) as exc:
            args = {}
            result = f"[error] invalid tool arguments: {exc}: {raw[:200]}"
        else:
            self.announce(name, args)
            allowed = (name in READ_ONLY or self.cfg.data["auto_approve"]
                       or self.approve(name, args))
            if not allowed:
                result = "[denied by user]"
            else:
                try:
                    result = call_tool(name, args,
                                       self.cfg.data["shell_timeout"],
                                       self.workdir)
                except ToolError as exc:
                    result = f"[error] {exc}"
        self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                              "name": name, "content": result})

    def _track_usage(self) -> None:
        # cheap approximation when providers don't return usage
        for m in self.messages[-1:]:
            content = m.get("content") or ""
            self.usage_total["completion_tokens"] += len(content) // 4

    # ------------------------------------------------------------------ misc
    def reset(self) -> None:
        self.new_session()

    def export_markdown(self) -> str:
        lines = [f"# TermuxAgent chat — {self.cfg.model()}",
                 "", f"- provider: {self.cfg.provider['name']}",
                 f"- model: {self.cfg.model()}", ""]
        for m in self.messages:
            role = m.get("role", "?")
            if role == "system":
                continue
            if role == "tool":
                lines.append(f"```tool {m.get('name', '')}\n{m.get('content', '')}\n```")
            elif role == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    fn = tc.get("function", {})
                    lines.append(f"> 🔧 **{fn.get('name')}** `{fn.get('arguments')}`")
            else:
                lines.append(f"## {role}\n\n{m.get('content', '')}\n")
        return "\n".join(lines)
