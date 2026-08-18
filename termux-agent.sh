#!/data/data/com.termux/files/usr/bin/bash
#
# Quick launcher — use this if you don't want to run install.sh.
#
#   bash termux-agent.sh
#
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[*] Creating local virtualenv..."
    python -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

exec python main.py "$@"
