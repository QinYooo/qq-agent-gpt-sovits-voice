#!/usr/bin/env bash
set -euo pipefail
TTS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$TTS_ROOT/scripts/python.sh"
tts_select_python
exec "$TTS_SELECTED_PYTHON" "$TTS_ROOT/scripts/setup.py" "$@"
