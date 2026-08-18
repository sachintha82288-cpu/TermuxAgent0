#!/usr/bin/env python3
"""
TermuxAgent0 - A lightweight AI agent that runs inside Termux on Android.

It supports:
  * Conversational chat with an LLM (OpenAI-compatible API).
  * Tool/function calling: shell commands, file read/write, Termux helpers.
  * Persistent conversation history in ~/.termux_agent/history.json.
  * A rich REPL with syntax highlighting and command completion.

Run with:
  python main.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent.app import TermuxAgentApp


DEFAULT_CONFIG_DIR = Path.home() / ".termux_agent"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def load_config(config_dir: Path) -> dict:
    """Load config from env vars and config.json. Env vars take precedence."""
    config_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = config_dir / "config.json"
    cfg: dict = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[!] Invalid config.json ({e}); using defaults.", file=sys.stderr)

    # Environment overrides
    env_map = {
        "OPENAI_API_KEY": "api_key",
        "OPENAI_BASE_URL": "base_url",
        "TERMUX_AGENT_MODEL": "model",
        "TERMUX_AGENT_SYS_PROMPT": "system_prompt",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val

    cfg.setdefault("base_url", DEFAULT_BASE_URL)
    cfg.setdefault("model", DEFAULT_MODEL)
    cfg.setdefault("system_prompt", SYSTEM_PROMPT_DEFAULT)
    return cfg


SYSTEM_PROMPT_DEFAULT = """\
You are TermuxAgent0, a helpful AI assistant running inside Termux on an Android device.
You have access to the user's Termux shell via a "shell" tool, and can read/write files.

Guidelines:
  * Be concise — the user is on a phone with a small screen.
  * Before running destructive commands (rm, mv overwrite, pkg uninstall), ask for
    confirmation and explain what will happen.
  * Prefer Termux package manager ("pkg install ...") over apt.
  * If a command is long-running, warn the user before running it.
  * When you write code, include the full file path.
  * You may use emoji sparingly to keep the output friendly.

Available tools:
  - shell(command: str, timeout: int = 10): run a shell command and return stdout/stderr.
  - read_file(path: str): read a text file and return its contents.
  - write_file(path: str, content: str): write text to a file (overwrites).
  - append_file(path: str, content: str): append text to a file.
  - ls(path: str = "."): list directory contents.
  - set_var(name: str, value: str): remember a user variable for this session.
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="termux-agent",
        description="AI agent that runs inside Termux on Android.",
    )
    p.add_argument(
        "-m", "--model",
        help="Model name (default: gpt-4o-mini or $TERMUX_AGENT_MODEL).",
    )
    p.add_argument(
        "--base-url",
        help="OpenAI-compatible base URL (default: https://api.openai.com/v1).",
    )
    p.add_argument(
        "--api-key",
        help="API key (or set OPENAI_API_KEY env var).",
    )
    p.add_argument(
        "-c", "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help=f"Config/history directory (default: {DEFAULT_CONFIG_DIR}).",
    )
    p.add_argument(
        "--no-stream", action="store_true",
        help="Disable streaming responses.",
    )
    p.add_argument(
        "--setup", action="store_true",
        help="Run the first-time setup wizard.",
    )
    p.add_argument(
        "prompt", nargs="*",
        help="Single prompt to run non-interactively (if omitted, enters REPL).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    config_dir = Path(args.config_dir).expanduser()
    cfg = load_config(config_dir)

    # CLI overrides
    if args.model:
        cfg["model"] = args.model
    if args.base_url:
        cfg["base_url"] = args.base_url
    if args.api_key:
        cfg["api_key"] = args.api_key

    api_key = cfg.get("api_key")
    if not api_key:
        print(
            "\n[!] No API key found. Set OPENAI_API_KEY or run:\n"
            "    python main.py --setup\n"
            "\nYou can use any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter,\n"
            "Ollama, llama.cpp, Gemini via gateway, etc.) by setting OPENAI_BASE_URL.\n",
            file=sys.stderr,
        )
        return 2

    app = TermuxAgentApp(
        api_key=api_key,
        base_url=cfg["base_url"].rstrip("/"),
        model=cfg["model"],
        system_prompt=cfg["system_prompt"],
        config_dir=config_dir,
        stream=not args.no_stream,
    )

    if args.setup:
        app.run_setup_wizard()
        return 0

    joined_prompt = " ".join(args.prompt).strip()
    if joined_prompt:
        return app.run_once(joined_prompt)
    return app.run_repl()


if __name__ == "__main__":
    raise SystemExit(main())
