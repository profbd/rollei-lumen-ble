#!/bin/bash
# Install this downloaded source project locally on first launch, then open the desk.
set -eu
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    if [ -n "${LUMEN_PYTHON:-}" ]; then
        LUMEN_INTERPRETER="$LUMEN_PYTHON"
    elif command -v python3.13 >/dev/null 2>&1; then
        LUMEN_INTERPRETER="$(command -v python3.13)"
    elif command -v python3 >/dev/null 2>&1; then
        LUMEN_INTERPRETER="$(command -v python3)"
    else
        echo "Please install Python 3.13 for macOS from https://www.python.org/downloads/macos/"
        echo "Then run this starter again."
        exit 1
    fi
    if ! "$LUMEN_INTERPRETER" -c 'import sys, tkinter; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
        echo "Python with Tk is needed. Install Python 3.13 using the macOS installer at:"
        echo "https://www.python.org/downloads/macos/"
        exit 1
    fi
    echo "Preparing Lumen Studio (first launch)…"
    "$LUMEN_INTERPRETER" -m venv .venv
fi
LUMEN_FINGERPRINT="$(.venv/bin/python -c 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("pyproject.toml").read_bytes()).hexdigest())')"
LUMEN_INSTALLED="$(cat .venv/.lumen-setup 2>/dev/null || true)"
if [ "$LUMEN_INSTALLED" != "$LUMEN_FINGERPRINT" ]; then
    echo "Installing Lumen Studio dependencies. Internet access is needed for this step."
    .venv/bin/python -m pip install --disable-pip-version-check .
    printf '%s\n' "$LUMEN_FINGERPRINT" > .venv/.lumen-setup
fi
if [ "${LUMEN_SETUP_ONLY:-0}" = 1 ]; then
    echo "Lumen Studio setup complete."
    exit 0
fi
exec .venv/bin/python src/studio_gui.py --config lamps.json --store studio.json
