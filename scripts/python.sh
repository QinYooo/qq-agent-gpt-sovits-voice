#!/usr/bin/env bash
# Sourced by the root entry scripts. No activation or current-directory assumption.
tts_select_python() {
  if [[ -n "${TTS_PYTHON:-}" ]]; then
    TTS_SELECTED_PYTHON="$TTS_PYTHON"
    return
  fi
  local candidate
  for candidate in "$TTS_ROOT/.venv/bin/python" python3.11 python3 python; do
    if "$candidate" -c 'import sys; assert sys.version_info[:2] == (3, 11)' >/dev/null 2>&1; then
      TTS_SELECTED_PYTHON="$candidate"
      return
    fi
  done
  printf '%s\n' 'Python 3.11 is required. Install Python 3.11 plus its venv package, or set TTS_PYTHON.' >&2
  return 1
}
export PYTHONUTF8=1 PYTHONUNBUFFERED=1
