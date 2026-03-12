#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CLI_SCRIPT="$SCRIPT_DIR/scripts/gdcpps.py"

if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_EXE="$SCRIPT_DIR/.venv/bin/python3"
elif [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_EXE="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_EXE=python
else
    echo "error: python3 or python was not found" >&2
    exit 1
fi

exec "$PYTHON_EXE" "$CLI_SCRIPT" "$@"
