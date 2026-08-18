# TermuxAgent0 🤖📱

**A lightweight AI agent that runs inside Termux on Android.**

TermuxAgent0 gives you a chat-style REPL backed by any OpenAI-compatible LLM
(OpenAI, Groq, OpenRouter, Ollama, llama.cpp, etc.) with built-in tools so the
model can run shell commands, read/write files, and navigate your Termux
environment — right from your phone.

## ✨ Features

- 💬 **Conversational REPL** with streaming responses, rich Markdown rendering,
  and persistent input history.
- 🔧 **Tool calling** out of the box: `shell`, `read_file`, `write_file`,
  `append_file`, `ls`, `pwd`, `set_var`.
- 🛡 **Safety nets**: dangerous commands (e.g. `rm -rf /`, `mkfs`, fork bombs)
  are blocked; destructive ops are flagged to the user in the system prompt.
- 🧠 **Context memory**: conversation history persists across sessions in
  `~/.termux_agent/history.json`. Save/load named conversations with `/save`
  and `/load`.
- 🔌 **Works with any OpenAI-compatible endpoint** — just set `OPENAI_BASE_URL`.
- 🪶 **Lightweight dependencies**: only `requests`, `rich`, and `prompt_toolkit`.

## 📦 Installation (Termux)

### Option 1 — Installer script (recommended)

```bash
pkg update && pkg upgrade -y
pkg install git python -y
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0
bash install.sh
```

The installer:

1. Installs `python` and `git` from Termux repos.
2. Creates an isolated virtualenv at `~/.termux_agent/venv`.
3. Installs Python deps.
4. Drops a `termux-agent` launcher onto your `$PATH`.

### Option 2 — Quick run (no install)

```bash
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0
bash termux-agent.sh
```

This creates a `.venv` inside the repo directory and launches the agent.

## 🔑 Configuration

Provide your API key one of these ways:

```bash
# 1. Environment variable (recommended; add to ~/.bashrc to persist)
export OPENAI_API_KEY=sk-...

# 2. Run the setup wizard — stores config at ~/.termux_agent/config.json
termux-agent --setup

# 3. One-off CLI flags
termux-agent --api-key sk-... --model gpt-4o-mini --base-url https://api.openai.com/v1
```

### Using other providers

Point `OPENAI_BASE_URL` at any OpenAI-compatible server:

| Provider  | Base URL                            | Example model               |
|-----------|-------------------------------------|-----------------------------|
| OpenAI    | `https://api.openai.com/v1`         | `gpt-4o-mini`               |
| Groq      | `https://api.groq.com/openai/v1`    | `llama-3.1-70b-versatile`   |
| OpenRouter| `https://openrouter.ai/api/v1`      | `openai/gpt-4o-mini`        |
| Ollama    | `http://localhost:11434/v1`         | `llama3`                    |

Example with Groq:

```bash
export OPENAI_API_KEY=gsk_...
export OPENAI_BASE_URL=https://api.groq.com/openai/v1
export TERMUX_AGENT_MODEL=llama-3.1-70b-versatile
termux-agent
```

## ▶️ Usage

### Interactive REPL

```bash
termux-agent
```

Inside the REPL:

| Command         | What it does                                  |
|-----------------|-----------------------------------------------|
| `/help`         | Show all commands                             |
| `/clear`        | Reset the conversation context                |
| `/history`      | Show number of messages in context            |
| `/model <name>` | Switch model for this session                 |
| `/save <name>`  | Save conversation to `saves/<name>.json`      |
| `/load <name>`  | Load a saved conversation                     |
| `/exit` / `/quit` | Exit (or use `Ctrl-D` / `Ctrl-C`)           |

### One-shot (non-interactive)

```bash
termux-agent "list files in the current directory and tell me what they are"
termux-agent --no-stream "write a python script that prints hello world to hello.py"
```

## 🧰 Available Tools (for the LLM)

- **shell(command, timeout=10)** — run any shell command (max 120s).
- **read_file(path)** — read a text file (truncated if huge).
- **write_file(path, content)** — create/overwrite a file.
- **append_file(path, content)** — append to a file.
- **ls(path='.')** — list a directory.
- **pwd()** — print working directory.
- **set_var(name, value)** — remember a variable in the session env.

> ⚠️ Built-in blocklist refuses obviously destructive patterns like
> `rm -rf /`, fork bombs, and raw `dd`/`mkfs` calls. Always review commands
> before saying "yes" when the agent asks for confirmation.

## 🏗 Project structure

```
TermuxAgent0/
├── agent/
│   ├── __init__.py
│   ├── app.py          # REPL + slash commands
│   ├── llm.py          # OpenAI-compatible chat client + tool loop
│   └── tools.py        # Shell / file / directory tools + schemas
├── install.sh          # One-shot Termux installer
├── termux-agent.sh     # No-install launcher
├── main.py             # CLI entry point
├── requirements.txt
├── LICENSE             # MIT
└── README.md
```

## 🛣 Roadmap

- [ ] Termux:API integration (SMS, notifications, camera, clipboard).
- [ ] Voice input via `termux-speech-to-text`.
- [ ] Per-project workspaces with sandboxed tool permissions.
- [ ] Built-in RAG over local files.

## 📄 License

MIT — see [LICENSE](./LICENSE).

## 🙋 Troubleshooting

- **`No API key found`**: set `OPENAI_API_KEY` or run `termux-agent --setup`.
- **Rich/prompt_toolkit import errors**: re-run `bash install.sh` (it sets up
  the venv) or `pip install -r requirements.txt`.
- **Slow responses on mobile**: use a faster model (e.g. `gpt-4o-mini`,
  `llama-3.1-8b-instant`) or a local endpoint.
