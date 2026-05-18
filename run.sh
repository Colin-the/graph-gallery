#!/usr/bin/env bash
# Start the Graph Gallery server.
#
# On a regular machine: creates .venv/ locally and installs Flask automatically.
# On nibi (Compute Canada CVMFS): activate .venv_stats first, or this script
#   falls back to it automatically.
#
# Usage:
#   ./run.sh             # serves on http://localhost:8000
#   PORT=9000 ./run.sh   # different port

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ ! -f graphs_manifest.json ]; then
    echo "ERROR: graphs_manifest.json not found."
    echo "Copy the full graph-gallery/ directory including static/graphs/ and graphs_manifest.json."
    exit 1
fi

# --- Resolve a Python that has Flask ---

LOCAL_VENV="$DIR/.venv"
NIBI_VENV="/home/ccampb47/work/MIMIC_Extract/.venv_stats"

PYTHON=""

# 1. Current shell's python3 already has Flask (activated venv or system install)
if python3 -c "import flask" 2>/dev/null; then
    PYTHON="$(which python3)"

# 2. Our managed local .venv already exists and has Flask
elif [ -f "$LOCAL_VENV/bin/python3" ] && "$LOCAL_VENV/bin/python3" -c "import flask" 2>/dev/null; then
    PYTHON="$LOCAL_VENV/bin/python3"

# 3. CVMFS / Compute Canada: skip local venv (won't work), use .venv_stats
elif [[ "$(python3 -c 'import sys; print(sys.executable)')" == /cvmfs/* ]]; then
    if [ -f "$NIBI_VENV/bin/python3" ] && "$NIBI_VENV/bin/python3" -c "import flask" 2>/dev/null; then
        PYTHON="$NIBI_VENV/bin/python3"
    else
        echo "ERROR: On nibi but .venv_stats Flask not found."
        echo "Run: source $NIBI_VENV/bin/activate"
        exit 1
    fi

# 4. Regular machine: create a local venv
elif python3 -m venv "$LOCAL_VENV" && [ -f "$LOCAL_VENV/bin/pip" ]; then
    echo "Installing Flask into .venv/ ..."
    "$LOCAL_VENV/bin/pip" install -r "$DIR/requirements.txt" --quiet
    PYTHON="$LOCAL_VENV/bin/python3"

else
    echo ""
    echo "ERROR: Could not set up Python with Flask."
    echo "Please create a venv manually and install dependencies:"
    echo "  python3 -m venv .venv && .venv/bin/pip install flask && .venv/bin/python3 app/server.py"
    exit 1
fi

PORT="${PORT:-8000}"
echo "Starting Graph Gallery on http://localhost:${PORT}"
PORT="${PORT}" "$PYTHON" app/server.py
