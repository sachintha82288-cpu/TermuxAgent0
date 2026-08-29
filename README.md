# TermuxAgent0

**An AI agent that lives in your Termux terminal.** Ask it in natural language;
it plans, runs shell commands, reads/edits/writes files, checks the results and
keeps going until the task is done.

- **100% standard library** — Python 3 only, no `pip install` of anything.
- **Any OpenAI-compatible API** — Groq (free tier, fastest on phones),
  OpenRouter, OpenAI, Together, or a local **Ollama** server.
- **Streaming replies**, a tool-use agent loop, shell approval prompts,
  conversation history that survives restarts, and an interactive REPL.
- Works on Termux, Linux and macOS.

---

## Quick start (Termux) 🇱🇰

```bash
pkg update -y && pkg install -y git python
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0
sh install.sh          # Python check + 'termuxagent' command + setup wizard
```

විශාර්ඩ් එකේදී provider එක තෝරන්න (Groq නොමිලේ, වේගවත්), API key එක දාන්න
(https://console.groq.com/keys — නොමිලේ ගන්න පුළුවන්), ඊට පස්සේ:

```bash
termuxagent           # chat එක start කරන්න
termuxagent "මේ folder එකේ තියෙන files මොනවාද කියලා බලලා විස්තර කරන්න"
termuxagent -y "python ප්‍රොජෙක්ට් එකක් scaffold කරලා tests run කරන්න"
```

> **Local & private?** Use Ollama: pick provider 4 in `--setup`, run
> `termux-setup-storage` + `ollama serve` on your machine, no API key needed.

## Install (Linux / macOS)

```bash
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0
python3 -m termuxagent --setup     # writes ~/.termuxagent/config.json
bin/termuxagent                    # or: python3 -m termuxagent
```

Optional: symlink the launcher onto your PATH:

```bash
ln -s "$PWD/bin/termuxagent" ~/.local/bin/termuxagent
```

## Usage

```
termuxagent [options] [prompt]

  (no prompt)            start the interactive REPL
  "do something"         one-shot mode: run the task, print the answer, exit
  -y, --yes              auto-approve shell commands (needed in one-shot mode)
  -C, --chdir PATH       work in this directory
  -m, --model NAME       override the model for this run
  --base-url URL         override the API endpoint
  --no-tools             plain chat, no shell/file access
  --resume               load the last saved conversation
  --setup                re-run the configuration wizard
  --version
```

Environment variables (override the config file):
`TERMUXAGENT_API_KEY`, `TERMUXAGENT_BASE_URL`, `TERMUXAGENT_MODEL`,
`TERMUXAGENT_HOME` (config/history directory, default `~/.termuxagent`).

### REPL commands

| Command        | What it does                                         |
|----------------|------------------------------------------------------|
| `/help`        | list commands                                        |
| `/reset`       | forget the current conversation                      |
| `/history`     | message count in session                             |
| `/cd PATH`     | change the working directory tools operate in        |
| `/auto`        | toggle auto-approve for shell commands               |
| `/model NAME`  | switch model                                         |
| `/config`      | show current config (key masked)                     |
| `/save`        | persist conversation now (also auto-saved on exit)   |
| `/clear`       | wipe saved history from disk                         |
| `/exit`        | quit                                                 |

## What the agent can do

Tools the model may call (OpenAI-style function tools):

- **`shell`** — runs a command via your shell (`sh`/`bash`/`$SHELL`), returns
  stdout, stderr and exit code. In the REPL, shell commands ask for approval
  first (`y` = once, `a` = always this session); in one-shot mode they are
  denied unless you pass `-y`.
- **`read_file`** — read a text file (large files truncated).
- **`write_file`** — create/overwrite a file (parent dirs created).
- **`edit_file`** — exact, unique find-and-replace (ambiguous edits rejected).
- **`list_dir`** — directory listing with directories marked.

The loop is capped at 12 tool steps per request; every tool error is returned
to the model as a message so it can recover instead of crashing.

## Safety

- Shell is the only destructive tool and it is gated behind an approval prompt
  by default (and fully blocked in non-interactive one-shot mode without `-y`).
- Your API key is stored in `~/.termuxagent/config.json` with `chmod 600`.
- Tools operate relative to the working directory; the agent never asks you
  for credentials.
- Review what it runs: every tool call is printed (`  . shell: ...`) before
  execution.

## Project layout

```
termuxagent/
  __init__.py     version
  __main__.py     CLI entry point (python -m termuxagent)
  config.py       config JSON, storage paths, setup wizard
  history.py      conversation persistence
  llm.py          OpenAI-compatible streaming client (stdlib urllib)
  tools.py        shell + read/write/edit/list tools and JSON schemas
  agent.py        the tool-use agent loop
  repl.py         interactive REPL with slash commands
  ui.py           tiny colour/output helpers
bin/termuxagent   launcher script
install.sh        Termux/Linux installer
tests/            unittest suite (27 tests, no network)
```

## Development

```bash
python3 -m unittest discover -s tests -v
```

No third-party dependencies are needed to run or test.

## License

MIT
