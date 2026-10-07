#!/bin/zsh
set -eu
cd "$(dirname "$0")"
# Keep failures readable instead of closing the only window with the error.
TRAPEXIT() {
  local result=$?
  if (( result != 0 )); then
    print "\nHost stopped with an error (exit $result). The details are above."
  fi
  if [[ -t 0 ]]; then read '?Press Enter to close.'; fi
}
print 'Starting Codespace Desktop 0.2.2. The first launch can take a moment…'
if [[ -x "./Codespace Desktop Host" ]]; then
  "./Codespace Desktop Host" "$@"
else
  if ! command -v python3 >/dev/null 2>&1; then
    print 'Install Python 3.12 or newer from https://www.python.org/downloads/macos/ and run this again.'
    exit 1
  fi
  python3 -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12 or newer is required"'
  if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python host.py "$@"
fi
