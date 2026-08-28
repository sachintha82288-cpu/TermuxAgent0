"""Entry point: ``python -m termuxagent [options] [prompt]``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .agent import Agent
from .config import Config, config_path, is_configured, setup_wizard
from .llm import LLMError
from .repl import Repl
from .ui import c, error, info, tool_call, warn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termuxagent",
        description="TermuxAgent0 — an AI agent with shell and file tools that "
        "runs in your terminal (Termux/Linux/macOS). Standard library only.",
    )
    parser.add_argument("prompt", nargs="*", help="One-shot prompt. With no prompt, starts the interactive REPL.")
    parser.add_argument("-m", "--model", help="Model name (overrides config).")
    parser.add_argument("--base-url", help="API base URL (overrides config).")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Auto-approve tool use (non-interactive mode). Without it, shell commands in one-shot mode are denied.")
    parser.add_argument("-C", "--chdir", dest="chdir", default=None,
                        help="Working directory for the agent (default: current directory).")
    parser.add_argument("--no-tools", action="store_true", help="Disable all tools (plain chat).")
    parser.add_argument("--resume", action="store_true",
                        help="Load the saved conversation (REPL: on startup; one-shot: as context).")
    parser.add_argument("--setup", action="store_true", help="Run the configuration wizard and exit.")
    parser.add_argument("--version", action="version", version=f"TermuxAgent0 {__version__}")
    return parser


def run_oneshot(cfg: Config, prompt: str, workdir: Path, resume: bool, yes: bool) -> int:
    def on_content(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def announce(name: str, args: dict) -> None:
        summary = args.get("command", args.get("path", ""))
        tool_call(name, str(summary).replace("\n", " ")[:100])

    def approve(name: str, args: dict) -> bool:
        if name != "shell" or yes:
            return True
        warn("shell command skipped in one-shot mode (re-run with -y to allow it):")
        warn(f"  $ {args.get('command', '')}")
        return False

    agent = Agent(cfg, workdir=workdir, on_content=on_content, approve=approve, announce=announce)
    if resume:
        from .history import load_history

        history = load_history()
        if history:
            agent.load_history(history)
            info(f"Loaded {len(history)} saved messages as context.")

    try:
        reply = agent.chat(prompt)
    except LLMError as exc:
        error(str(exc))
        return 1
    print()
    agent.persist()
    return 0 if "[error]" not in reply else 1


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load()

    if args.model:
        cfg.model = args.model
    if args.base_url:
        cfg.base_url = args.base_url.rstrip("/")
    if args.no_tools:
        cfg.tools_enabled = []

    workdir = Path(args.chdir).expanduser().resolve() if args.chdir else Path.cwd()
    if not workdir.is_dir():
        error(f"not a directory: {workdir}")
        return 1

    if args.setup:
        setup_wizard(cfg)
        return 0

    if not is_configured(cfg):
        info(f"No configuration found at {config_path()}.")
        try:
            setup_wizard(cfg)
        except (KeyboardInterrupt, EOFError):
            print()
            error("Setup cancelled. Re-run with --setup or set TERMUXAGENT_API_KEY.")
            return 1

    if args.prompt:
        prompt = " ".join(args.prompt)
        try:
            return run_oneshot(cfg, prompt, workdir, resume=args.resume, yes=args.yes)
        except KeyboardInterrupt:
            print()
            warn("Interrupted.")
            return 130

    Repl(cfg, workdir=workdir, resume=args.resume).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
