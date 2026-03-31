#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  CHARLES — Lanceur universel  (macOS / Linux)
#  Usage : ./start.sh
# ══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Cherche Python 3 ──────────────────────────────────────────
PYTHON=""

for candidate in python3 python3.12 python3.11 python3.10 python3.9 python3.8 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(sys.version_info[0])" 2>/dev/null || echo "0")
        if [ "$version" = "3" ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo " ✖  Python 3 introuvable."
    echo ""
    echo " Sur macOS   → brew install python  ou  https://www.python.org"
    echo " Sur Ubuntu  → sudo apt install python3"
    echo " Sur Fedora  → sudo dnf install python3"
    echo ""
    exit 1
fi

echo ""
echo " CHARLES — Lanceur universel"
echo " Python utilisé : $(command -v "$PYTHON") ($("$PYTHON" --version))"
echo ""

# ── Lance start.py ────────────────────────────────────────────
exec "$PYTHON" "$SCRIPT_DIR/start.py" "$@"
