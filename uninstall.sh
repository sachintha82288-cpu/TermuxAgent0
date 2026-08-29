#!/usr/bin/env bash
# Remove everything TermuxAgent installed.
set -e
GREEN='\033[32m'; CYAN='\033[36m'; YELLOW='\033[33m'; RESET='\033[0m'
say() { printf "${GREEN}[+]${RESET} %s\n" "$1"; }
ask() { printf "${CYAN}[?]${RESET} %s" "$1"; }
warn() { printf "${YELLOW}[!]${RESET} %s\n" "$1"; }

ask "remove ~/.termux-agent and the agent/Agent commands? [y/N] "
read -r REPLY
if [ "$REPLY" != "y" ] && [ "$REPLY" != "Y" ]; then
    say "cancelled."
    exit 0
fi

rm -rf "$HOME/.termux-agent"
for BIN_DIR in "${PREFIX:-/data/data/com.termux/files/usr}/bin" "$HOME/.local/bin" "$HOME/bin" "/usr/local/bin"; do
    [ -d "$BIN_DIR" ] || continue
    rm -f "$BIN_DIR/agent" "$BIN_DIR/Agent" 2>/dev/null || true
done
say "TermuxAgent removed. Chat exports stay in ~/termux-agent-chats if you had any."
