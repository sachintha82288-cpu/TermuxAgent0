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

**ඔබේ Termux terminal එක ඇතුළේ වැඩ කරන ඇත්ත AI Agent කෙනෙක්.**
An AI agent that actually *lives* in your Termux terminal — it plans, runs
shell commands, reads/edits files, checks results and keeps going until your
task is done. Ask in **Sinhala or English**.

- ⚡ **27 API providers built in** — Groq, OpenAI, Gemini, Claude, Grok,
  DeepSeek, OpenRouter, Mistral, Cerebras, Ollama (local)… full list below
- 🎨 **12 තේමා 12 themes** — neon, cyberpunk, matrix, dracula… සුපිරි banner +
  gradients + arrow-key menus
- 🛠 **Real tools** — `shell`, `read_file`, `write_file`, `edit_file`, `list_dir`
  with safety checks and approve-before-run
- 📦 **100% Python stdlib** — `pip install` අවශ්‍ය නෑ, python3 ප්‍රමාණවතයි
- 🔄 Streaming replies, conversation history, ```run``` one-tap command blocks
- 🇱🇰 Made for Termux, works on Linux & macOS too

---

## ⚡ Install (Termux)

```bash
pkg update -y && pkg install -y git python
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0
bash install.sh
```

One-liner install:

```bash
curl -fsSL https://raw.githubusercontent.com/sachintha82288-cpu/TermuxAgent0/main/install.sh | bash
```

Install වුණාම **Termux එකේ `Agent` type කරන්න** — agent එක open වෙනවා
(`agent` වලිනුත් පුළුවන්). First run එකේදීම setup wizard එක එයි:

1. **Provider එක තෝරන්න** — `Groq` recommend කරනවා (නොමිලේ, ගොඩක් වේගවත්)
2. **API key එක paste කරන්න** — [console.groq.com/keys](https://console.groq.com/keys)
   එකෙන් නොමිලේ ගන්න පුළුවන්
3. **Model එක තෝරන්න** — list එක automatically එනවා
4. **Theme එක තෝරන්න** — live preview එකක් එක්කම

Done! `Agent` type කරලා chat කරන්න. 🎉

## 🚀 Use

```bash
Agent                    # chat start කරන්න  (ලොකු A එකෙන් හෝ පොඩි එකෙන්)
Agent ask "battery status එක බලලා කියන්න" -y     # one-shot mode
Agent setup              # provider / key / model / theme මාරු කරන්න
Agent doctor             # ප්‍රශ්නයක් තියෙනවද බලන්න
Agent providers          # සියලු providers 27 බලන්න
Agent theme cyberpunk    # theme එක මාරු කරන්න
```

Chat එක ඇතුළේ:

| Command | වැඩේ |
|---|---|
| `/help` | සියලු commands |
| `/provider` | API provider එක මාරු කරන්න (27) |
| `/model`, `/models` | model එක මාරු කරන්න / list එක බලන්න |
| `/theme` | theme එක මාරු කරන්න (live preview) |
| `/tools`, `/auto` | tools on/off · auto-approve on/off |
| `/new`, `/save` | අලුත් chat · markdown export |
| `!ls -la` | shell command එකක් direct run කරන්න |
| `/exit` | පිටවෙන්න (history auto-save වෙනවා) |

### උදාහරණ

```text
you ❯ මේ folder එකේ python project එකක් හදලා test run කරන්න
  🔧 shell python3 -m venv .venv && .venv/bin/pip install pytest
  🔧 write_file calculator.py (214 chars)
  🔧 shell .venv/bin/python -m pytest -q
calculator project ready ✓ — 5 tests passed
```

## ☁ Supported providers (27)

| Cloud | Local / Custom |
|---|---|
| Groq · OpenAI · Anthropic (Claude) · Google Gemini · xAI (Grok) · DeepSeek · OpenRouter · Mistral · Together AI · Cerebras · SambaNova · Fireworks · Perplexity · Hyperbolic · Novita · Lambda · Moonshot (Kimi) · Alibaba Qwen · Cohere · NVIDIA NIM · Hugging Face · Glama · Chutes | Ollama · LM Studio · llama.cpp · **Custom** (ඕනම OpenAI-compatible URL එකක්) |

මාරු කරන්න: `Agent provider groq` · `Agent provider ollama` · ඕනම එකක්.
Local (Ollama/LM Studio) වලට API key ඕන නෑ — සම්පූර්ණයෙන්ම private.

## 🛠 What the agent can do

Model එට call කරන්න පුළුවන් tools (OpenAI function calling):

- **`shell`** — Termux එකේ command run කරනවා (`pkg install`, `git`,
  `termux-battery-status`, `termux-notification`…) — කලින් confirm කරනවා
- **`read_file` / `write_file` / `edit_file` / `list_dir`** — file operations
  (overwrite කරන්න කලින් `.bak` backup එකක් තියෙනවා)

Safety:

- විනාශකාරී commands (`rm -rf /`, `mkfs`, `shutdown`…) block වෙනවා
- shell/write actions වලට ඔබගේ approval එක ඕන (`-y` / `/auto` වලින් skip කරන්න පුළුවන්)
- API keys `~/.termux-agent/config.json` එකේ `chmod 600` එකෙන් save වෙනවා
- Tool function calling support නැති providers (Perplexity) වලට ```run``` blocks එකෙන් one-tap execution තියෙනවා

## 🖥 Linux / macOS

```bash
git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
cd TermuxAgent0
bash install.sh        # installs ~/.local/bin/agent + Agent
```

නැත්තම් repo එකෙන් direct: `python3 run.py` හෝ `python3 -m termuxagent`.

## 🎨 Themes

`neon` (default) · `cyberpunk` · `matrix` · `dracula` · `nord` · `sunset` ·
`ocean` · `sakura` · `ruby` · `gold` · `vaporwave` · `mono`

```bash
Agent theme matrix     # හෝ chat එක ඇතුළේ /theme
```

## 📁 Project layout

```
termuxagent/
  theme.py       12 themes · gradients · block-letter banners · boxes
  providers.py   27-provider catalogue (URLs, key links, defaults)
  ui.py          arrow-key menus · spinner · styled prompts
  setup.py       first-run wizard (provider → key → model → theme)
  config.py      ~/.termux-agent/config.json (chmod 600)
  llm.py         streaming OpenAI-compatible client (stdlib urllib)
  tools.py       shell/file tools + safety blocklist
  agent.py       the tool-use agent loop
  repl.py        interactive chat · slash commands · ```run``` blocks
  cli.py         agent setup|ask|providers|doctor|theme|model|config|uninstall
run.py           bootstrap launcher
install.sh       installs `agent` + `Agent` commands
tests/           24 tests incl. a mock OpenAI server (no network)
```

## 🔧 Development

```bash
python3 -m unittest discover -s tests -v
```

No dependencies, no network needed for tests (a mock OpenAI-compatible
server exercises streaming + tool calls end to end).

## License

MIT
