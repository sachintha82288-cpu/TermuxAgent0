"""Interactive read-eval-print loop for TermuxAgent0."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .agent import Agent
from .config import Config
from .history import clear_history, load_history
from .llm import LLMError
from .ui import BOLD, CYAN, DIM, GREEN, YELLOW, c, error, info, success, tool_call, warn

HELP = """
commands:
  /help       show this help
  /reset      forget the conversation and start over
  /history    show the number of stored messages
  /cd PATH    change the working directory used by tools
  /auto       toggle auto-approve for shell commands
  /model NAME switch model (this session)
  /config     show current configuration
  /save       persist the conversation now (also saved on exit)
  /clear      wipe saved conversation history from disk
  /exit       leave the agent
""".strip()


class Repl:
    def __init__(self, cfg: Config, workdir: Optional[Path] = None, resume: bool = False) -> None:
        self.cfg = cfg
        self.workdir = (workdir or Path.cwd()).resolve()
        self.resume = resume
        self.agent: Optional[Agent] = None

    # ---------------------------------------------------------------- output
    @staticmethod
    def _on_content(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def _announce(self, name: str, args: dict) -> None:
        if name == "shell":
            summary = args.get("command", "")
        else:
            summary = args.get("path", args.get("content", ""))
            summary = str(summary).replace("\n", " ")
            if len(summary) > 80:
                summary = summary[:77] + "..."
        tool_call(name, summary)

    def _approve(self, name: str, args: dict) -> bool:
        if name != "shell" or self.cfg.auto_approve_shell:
            return True
        command = args.get("command", "")
        print(c(f"  shell wants to run: {command}", YELLOW))
        try:
            answer = input(c("  approve? [y]es / [N]o / [a]lways: ", YELLOW)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if answer in ("a", "always"):
            self.cfg.auto_approve_shell = True
            return True
        return answer in ("y", "yes")

    # ------------------------------------------------------------------ run
    def run(self) -> None:
        self.agent = Agent(
            self.cfg,
            workdir=self.workdir,
            on_content=self._on_content,
            approve=self._approve,
            announce=self._announce,
        )
        if self.resume:
            history = load_history()
            if history:
                self.agent.load_history(history)
                info(f"Resumed {len(history)} saved messages. (/reset to start fresh)")

        print(c(f"TermuxAgent0 v{__version__}", BOLD + GREEN))
        print(c(f"  model: {self.cfg.model}   dir: {self.agent.workdir}", DIM))
        print(c("  type /help for commands, /exit to quit.", DIM))
        print()

        while True:
            try:
                user = input(c("agent › ", CYAN + BOLD)).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue
            if user.startswith("/"):
                if self._handle_command(user):
                    break
                continue
            self._send(user)

        try:
            self.agent.persist()
            success("Conversation saved.")
        except OSError as exc:
            warn(f"Could not save history: {exc}")
        info("Bye!")

    def _send(self, user: str) -> None:
        assert self.agent is not None
        try:
            self.agent.chat(user)
        except LLMError as exc:
            error(str(exc))
        except KeyboardInterrupt:
            print()
            warn("Interrupted.")
        print()
        print()

    # ------------------------------------------------------------- commands
    def _handle_command(self, line: str) -> bool:
        """Return True when the REPL should exit."""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            return True
        if cmd == "/help":
            print(HELP)
        elif cmd == "/reset":
            assert self.agent is not None
            self.agent.reset()
            success("Conversation reset.")
        elif cmd == "/history":
            assert self.agent is not None
            n = len(self.agent.messages) - 1
            info(f"{n} message(s) in this session.")
        elif cmd == "/cd":
            if not arg:
                warn("usage: /cd PATH")
            else:
                target = Path(arg).expanduser()
                if not target.is_dir():
                    error(f"not a directory: {target}")
                else:
                    self.workdir = target.resolve()
                    assert self.agent is not None
                    self.agent.workdir = self.workdir
                    os.chdir(self.workdir)
                    success(f"Working directory: {self.workdir}")
        elif cmd == "/auto":
            self.cfg.auto_approve_shell = not self.cfg.auto_approve_shell
            if self.cfg.auto_approve_shell:
                state = "ON (all shell commands run without asking)"
            else:
                state = "OFF (shell commands ask first)"
            info(f"auto-approve: {state}")
        elif cmd == "/model":
            if not arg:
                warn(f"current model: {self.cfg.model}")
            else:
                self.cfg.model = arg
                success(f"model set to {arg}")
        elif cmd == "/config":
            key = self.cfg.api_key
            shown = (key[:6] + "...") if key and key != "not-needed" else key
            print(json.dumps(
                {
                    "base_url": self.cfg.base_url,
                    "model": self.cfg.model,
                    "api_key": shown,
                    "auto_approve_shell": self.cfg.auto_approve_shell,
                    "workdir": str(self.workdir),
                },
                indent=2,
            ))
        elif cmd == "/save":
            assert self.agent is not None
            self.agent.persist()
            success("Conversation saved.")
        elif cmd == "/clear":
            clear_history()
            assert self.agent is not None
            self.agent.reset()
            success("Saved history wiped and session reset.")
        else:
            warn(f"unknown command: {cmd} (try /help)")
        print()
        return False
