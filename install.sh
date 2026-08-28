#!/data/data/com.termux/files/usr/bin/sh
# TermuxAgent0 installer for Termux (also works on plain Linux/macOS).
#
#   curl -fsSL https://raw.githubusercontent.com/sachintha82288-cpu/TermuxAgent0/main/install.sh | sh
#
# or, after cloning:  sh install.sh
set -e

GREEN='\033[32m'; YELLOW='\033[33m'; CYAN='\033[36m'; RESET='\033[0m'
say() { printf "${GREEN}[+]${RESET} %s\n" "$1"; }
ask() { printf "${CYAN}[?]${RESET} %s" "$1"; }
warn() { printf "${YELLOW}[!]${RESET} %s\n" "$1"; }

# Find where the repo lives (the directory this script is in).
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------- dependencies
if command -v pkg >/dev/null 2>&1; then
    say "Termux detected — installing python via pkg..."
    pkg update -y
    pkg install -y python
elif ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found. Install Python 3.9+ with your package manager and re-run."
    exit 1
fi

PY=python3
say "Using $($PY --version 2>&1)"

# No third-party packages are required; verify the standard library imports.
$PY -c "import urllib.request, json, subprocess, argparse; print('stdlib OK')"

# ------------------------------------------------------------------ install cmd
BIN_DIR="$PREFIX/bin"
[ -d "$BIN_DIR" ] || BIN_DIR="/usr/local/bin"

TARGET="$BIN_DIR/termuxagent"
if [ -w "$BIN_DIR" ]; then
    cp "$SCRIPT_DIR/bin/termuxagent" "$TARGET"
    chmod +x "$TARGET"
    say "Installed launcher to $TARGET"
else
    warn "No write permission to $BIN_DIR."
    mkdir -p "$HOME/.local/bin"
    TARGET="$HOME/.local/bin/termuxagent"
    cp "$SCRIPT_DIR/bin/termuxagent" "$TARGET"
    chmod +x "$TARGET"
    say "Installed launcher to $TARGET"
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) warn "Add ~/.local/bin to your PATH (e.g. in ~/.bashrc):"
           warn "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
fi

# ----------------------------------------------------------------------- setup
say "Starting configuration wizard..."
$PY -m termuxagent --setup

cat <<EOF

${GREEN}TermuxAgent0 is installed.${RESET}

  start chatting:   ${CYAN}termuxagent${RESET}
  one question:     ${CYAN}termuxagent "list files in this directory and summarise them"${RESET}
  allow shell cmds: ${CYAN}termuxagent -y "install requests and test the import"${RESET}
  reconfigure:      ${CYAN}termuxagent --setup${RESET}

EOF
