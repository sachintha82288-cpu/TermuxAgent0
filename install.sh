#!/data/data/com.termux/files/usr/bin/bash
#
# install.sh - Install TermuxAgent0 inside Termux.
#
# Usage:
#   pkg install git python -y
#   git clone https://github.com/sachintha82288-cpu/TermuxAgent0.git
#   cd TermuxAgent0
#   bash install.sh
#
set -e

CYAN='\033[1;36m'
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}>>> TermuxAgent0 installer${NC}\n"

# 1) Make sure python and pip are available
echo -e "${YELLOW}>>> Updating packages and installing python + pip...${NC}"
pkg update -y
pkg upgrade -y
pkg install -y python git

# 2) Create a venv in the repo directory (keeps things tidy)
VENV_DIR="$HOME/.termux_agent/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}>>> Creating virtualenv at $VENV_DIR ...${NC}"
    python -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 3) Upgrade pip and install requirements
echo -e "${YELLOW}>>> Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r "$(dirname "$0")/requirements.txt"

# 4) Install a launcher script in ~/../usr/bin so `termux-agent` is on PATH
BIN_DIR="$PREFIX/bin"
LAUNCHER="$BIN_DIR/termux-agent"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${YELLOW}>>> Installing 'termux-agent' command to $BIN_DIR ...${NC}"
cat > "$LAUNCHER" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
source "$VENV_DIR/bin/activate"
exec python "$REPO_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"

echo
echo -e "${GREEN}✅ Installation complete!${NC}"
echo
echo -e "Next steps:"
echo -e "  1. ${CYAN}export OPENAI_API_KEY=sk-...${NC}  (or: ${CYAN}termux-agent --setup${NC})"
echo -e "  2. Run the agent: ${CYAN}termux-agent${NC}"
echo -e "  3. Use ${CYAN}/help${NC} inside the REPL to see commands."
echo
echo -e "Tip: add your API key to ~/.bashrc so it persists across sessions:"
echo -e "     echo 'export OPENAI_API_KEY=sk-...' >> ~/.bashrc"
