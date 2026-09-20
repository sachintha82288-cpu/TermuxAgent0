# TermuxAgent

```
████████╗ ███████╗ ██████╗  ███╗   ███╗ ██╗   ██╗ ██╗  ██╗
╚══██╔══╝ ██╔════╝ ██╔══██╗ ████╗ ████║ ██║   ██║ ╚██╗██╔╝
   ██║    █████╗   ██████╔╝ ██╔████╔██║ ██║   ██║  ╚███╔╝
   ██║    ██╔══╝   ██╔══██╗ ██║╚██╔╝██║ ██║   ██║ ██╔██╗
   ██║    ███████╗ ██║  ██║ ██║ ╚═╝ ██║ ╚██████╔╝ ██╔╝ ██╗
   ╚═╝    ╚══════╝ ╚═╝  ╚═╝ ╚═╝     ╚═╝  ╚═════╝  ╚═╝  ╚═╝
              █████╗   ██████╗  ███████╗ ███╗   ██╗ ████████╗
             ██╔══██╗ ██╔════╝  ██╔════╝ ████╗  ██║ ╚══██╔══╝
             ███████║ ██║  ███╗ █████╗   ██╔██╗ ██║    ██║
             ██╔══██║ ██║   ██║ ██╔══╝   ██║╚██╗██║    ██║
             ██║  ██║ ╚██████╔╝ ███████╗ ██║ ╚████║    ██║
             ╚═╝  ╚═╝  ╚═════╝  ╚══════╝ ╚═╝  ╚═══╝    ╚═╝
```

**An AI agent that lives in your Termux terminal.**

TermuxAgent doesn't just chat — it plans, runs shell commands, reads and edits
files, checks the results and keeps going until the job is done. It works with
27 API providers (or a fully local model), needs **nothing but Python**, and
looks great on a phone screen.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](#requirements)
[![Zero dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](#requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Platform: Termux · Linux · macOS](https://img.shields.io/badge/platform-Termux%20%7C%20Linux%20%7C%20macOS-orange)](#linux--macos)

---

## Table of contents

- [Highlights](#highlights)
- [Quick start (Termux)](#quick-start-termux)
- [Usage](#usage)
- [What the agent can do](#what-the-agent-can-do)
- [Supported providers](#supported-providers)
- [Themes](#themes)
- [Configuration](#configuration)
- [Safety](#safety)
- [Troubleshooting](#troubleshooting)
- [Linux / macOS](#linux--macos)
- [Project layout](#project-layout)
- [Development](#development)
- [Uninstall](#uninstall)
- [License](#license)

---

## Highlights

| | |
|---|---|
| 🤖 **A real agent** | Tool-use loop with `shell`, `read_file`, `write_file`, `edit_file`, `list_dir` — it acts, observes and adapts until the task is complete. |
| 📦 **Zero dependencies** | 100 % Python standard library. No `pip`, no `npm`, no virtualenv — the installer only makes sure Termux's `python` package is present. |
| ☁️ **27 providers, one client** | Groq, OpenAI, Anthropic, Gemini, xAI, DeepSeek, OpenRouter, Mistral, Cerebras… plus Ollama / LM Studio / llama.cpp locally, or any OpenAI-compatible URL. |
| 🎨 **Aurora theme** | 24-bit violet → cyan → mint gradient (auto-detected on Termux) plus 12 more palettes, live-preview theme picker and arrow-key menus. |
| 🛡 **Safe by default** | Every shell / write action is shown for approval, a regex blocklist refuses catastrophic commands, and API keys are stored `chmod 600`. |
| 📱 **Built for phones** | Compact banner on narrow screens, Unicode-aware boxes, Ctrl+C-friendly prompt, one-tap ```` ```run ```` blocks for providers without function calling. |
| 🔄 **Streaming & memory** | Live token streaming, reasoning-token display, resumable conversations (`agent -c`) and Markdown export. |

## Quick start (Termux)

One line — clones the repo, installs the `agent` command and launches the setup wizard:

```bash
curl -fsSL https://raw.githubusercontent.com/sachintha82288-cpu/TermuxAgent0/main/install.sh | bash
```

Or from a clone:

```bash
pkg install -y git python
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0 && bash install.sh
```

Then type **`agent`** (or `Agent`). On the first run a wizard walks you through it:

1. **Pick a provider** — a quick-start menu puts the free options first
   (Groq, Gemini, OpenRouter, Ollama); the full list of 27 is one keypress away.
2. **Paste your API key** — the wizard shows the sign-up link, offers to open it
   in your browser, and verifies the key immediately.
3. **Choose a model** — fetched live from the provider.
4. **Choose a theme** — with a live preview.

That's it. You're chatting in under a minute.

> **Requirements**
> Python 3.8 or newer. Nothing else. `install.sh` installs Termux's `python`
> package via `pkg` if it's missing; no third-party packages are ever pulled in.

## Usage

```bash
agent                          # open the chat
agent -c                       # resume the last conversation
agent ask "check battery" -y   # one-shot: do the task, print the answer, exit
agent setup                    # change provider / key / model / theme
agent doctor                   # diagnose problems (and offer to fix them)
agent providers                # list all 27 providers
agent models                   # list models on the current provider
agent theme aurora             # switch theme
agent provider ollama          # switch provider
agent model llama-3.1-8b-instant
agent config                   # show the active config (key masked)
```

Options: `-y/--yes` auto-approve tool actions · `-c/--continue` resume ·
`-C DIR` working directory · `-m MODEL` / `-p PROVIDER` one-off overrides ·
`--no-tools` plain chat.

### Inside the chat

| Command | What it does |
|---|---|
| `/help` | list all commands |
| `/provider` | switch API provider (asks for key/model if needed) |
| `/model [name]`, `/models` | switch model / list models from the API |
| `/theme [name]` | change theme with live preview |
| `/tools`, `/auto` | toggle tools · toggle auto-approve |
| `/system [text]` | show or set extra system instructions |
| `/new`, `/save`, `/stats` | fresh conversation · export Markdown · session stats |
| `!ls -la` | run a shell command directly |
| `/exit` | quit (history is saved automatically) |

Press **Ctrl+C** once to stop the current answer or clear the line; twice to exit.

### Example

```text
you ❯ create a python project here and run the tests
  🔧 shell python3 -m venv .venv && .venv/bin/pip install pytest
  🔧 write_file calculator.py (214 chars)
  🔧 write_file test_calculator.py (388 chars)
  🔧 shell .venv/bin/python -m pytest -q
Project ready ✓ — 5 tests passed.
```

## What the agent can do

The model is given five OpenAI-style function tools:

| Tool | Purpose |
|---|---|
| `shell` | Run a command in Termux/Linux — `pkg install`, `git`, `termux-battery-status`, `termux-notification`, network checks, scripts… stdin is closed and pagers/prompts are disabled so nothing hangs. |
| `read_file` | Read a text file (large files are truncated). |
| `write_file` | Create or overwrite a file — a `.bak` backup is kept when overwriting. |
| `edit_file` | Replace one exact, unique snippet in a file. |
| `list_dir` | List a directory with sizes. |

Read-only tools run immediately; `shell`, `write_file` and `edit_file` are
shown to you for approval first (skip with `-y` or `/auto`).

Providers without function calling (e.g. Perplexity) get the same power via
```` ```run ```` code blocks that the terminal offers to execute.

## Supported providers

| Cloud | Local / custom |
|---|---|
| Groq · OpenAI · Anthropic (Claude) · Google Gemini · xAI (Grok) · DeepSeek · OpenRouter · Mistral · Together AI · Cerebras · SambaNova · Fireworks · Perplexity · Hyperbolic · Novita · Lambda · Moonshot (Kimi) · Alibaba Qwen · Cohere · NVIDIA NIM · Hugging Face · Glama · Chutes | Ollama · LM Studio · llama.cpp · **Custom** (any OpenAI-compatible `/v1` URL — vLLM, LiteLLM, …) |

Switch any time with `agent provider <id>` or `/provider`. Keys are stored
per provider, so switching back and forth is instant. Local providers need
no key and never send data off your device.

## Themes

`aurora` (default) · `neon` · `cyberpunk` · `matrix` · `dracula` · `nord` ·
`sunset` · `ocean` · `sakura` · `ruby` · `gold` · `vaporwave` · `mono`

Aurora uses true 24-bit colour when the terminal supports it (Termux does; it's
detected automatically) and falls back to the closest 256-colour palette
otherwise. Set `TERMUXAGENT_TRUECOLOR=0` to force the fallback, or `NO_COLOR=1`
to disable colours entirely.

```bash
agent theme matrix        # or /theme inside the chat for a live preview
```

## Configuration

Everything lives in `~/.termux-agent/`:

| File | Contents |
|---|---|
| `config.json` | provider, per-provider API keys and models, theme, options (`chmod 600`) |
| `history.json` | last conversation (for `agent -c`) |
| `input-history` | prompt history for the ↑ key |
| `app/` | the installed copy of the program |

Useful keys in `config.json`: `temperature`, `max_steps` (tool steps per
request, default 12), `shell_timeout`, `timeout`, `stream`, `show_reasoning`,
`system_extra`.

Environment overrides: `TERMUXAGENT_PROVIDER`, `TERMUXAGENT_MODEL`,
`TERMUXAGENT_API_KEY`, `TERMUXAGENT_HOME`, plus each provider's own variable
(`GROQ_API_KEY`, `OPENAI_API_KEY`, …).

## Safety

- **Approve before run** — shell and write actions wait for your `y` unless you
  opt into `-y` / `/auto`.
- **Blocklist** — `rm -rf /`, `mkfs`, `dd … of=/dev/…`, `shutdown`/`reboot`,
  fork bombs, writes to block devices and similar are refused outright. The
  check is command-position aware, so `git commit -m "fix reboot bug"` is fine.
- **Non-interactive shell** — tool commands get no stdin and no pager, so a
  stray `apt` prompt can't hang the agent; timeouts report partial output.
- **Keys stay local** — stored `chmod 600`, shown masked, never logged, and the
  system prompt forbids the model from asking for them.
- **Interrupt-safe** — Ctrl+C mid-task leaves a valid transcript, so the next
  message just works.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `agent: command not found` | Open a new terminal (the installer adds the bin dir to your shell rc), or run `python3 ~/.termux-agent/app/run.py`. |
| `HTTP 401 — invalid API key?` | `agent setup` and paste the key again (without quotes). |
| `cannot reach …` | Check your connection; for local providers make sure the server is running (`ollama serve`). |
| `HTTP 429 — rate limited` | Wait a moment or pick a different model with `/model`. |
| `command timed out … waiting for input` | The command needed interactive input — ask the agent to use non-interactive flags such as `-y`. |
| Colours look wrong | `agent theme mono`, or `NO_COLOR=1 agent`. |
| Anything else | `agent doctor` checks Python, config, key, model and API reachability, and offers to rerun setup. |

## Linux / macOS

```bash
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0 && bash install.sh      # installs ~/.local/bin/agent (+ Agent)
```

Or run straight from the checkout: `python3 run.py` / `python3 -m termuxagent`.
`pip install .` also works and provides the `agent` entry point — still with
zero runtime dependencies.

## Project layout

```
termuxagent/
  theme.py       13 themes · truecolor gradients · Unicode-aware boxes · banner
  providers.py   27-provider catalogue (URLs, key links, default models)
  ui.py          arrow-key menus with scrolling · spinner · prompts
  setup.py       first-run wizard (quick-start → key check → model → theme)
  config.py      ~/.termux-agent/config.json (chmod 600, self-repairing)
  llm.py         streaming OpenAI-compatible client (urllib only)
  tools.py       shell + file tools, blocklist, non-interactive execution
  agent.py       the tool-use loop with interrupt-safe transcripts
  repl.py        interactive chat · slash commands · ```run blocks
  cli.py         agent setup|ask|providers|doctor|theme|model|config|uninstall
run.py           bootstrap launcher
install.sh       installer (clone or curl | bash) — writes `agent` + `Agent`
uninstall.sh     removes everything
tests/           30 tests incl. a mock OpenAI server (no network needed)
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

The test suite needs no network: a built-in mock OpenAI-compatible server
exercises streaming, tool calls and error handling end to end.

## Uninstall

```bash
agent uninstall          # or: bash uninstall.sh
```

Removes `~/.termux-agent` (config, keys, history, app copy) and the `agent` /
`Agent` launchers. Exported chats in `~/termux-agent-chats` are left alone.

## License

MIT — see [LICENSE](LICENSE).
