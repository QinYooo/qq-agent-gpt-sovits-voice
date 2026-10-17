#!/usr/bin/env bash
set -euo pipefail
TTS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$TTS_ROOT/.venv/bin/python" ]]; then
  printf '%s\n' 'Run bash setup.sh first.' >&2
  exit 1
fi
export PYTHONUTF8=1
exec "$TTS_ROOT/.venv/bin/python" "$TTS_ROOT/tts.py" "$@"
