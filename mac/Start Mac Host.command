#!/bin/zsh
set -eu
cd "$(dirname "$0")"
if [[ -x "./Codespace Desktop Host" ]]; then
  "./Codespace Desktop Host"
else
  if ! command -v python3 >/dev/null 2>&1; then
    print 'Install Python 3.12 or newer from https://www.python.org/downloads/macos/ and run this again.'
    read '?Press Enter to close.'
    exit 1
  fi
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python host.py
fi
read '?Press Enter to close.'
