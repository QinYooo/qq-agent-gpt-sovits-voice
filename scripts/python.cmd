@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
if defined TTS_PYTHON goto custom
if exist "%~dp0..\.venv\Scripts\python.exe" (
  "%~dp0..\.venv\Scripts\python.exe" %*
  exit /b
)
py -3.11 -c "import sys; assert sys.version_info[:2] == (3,11)" >nul 2>nul
if not errorlevel 1 (
  py -3.11 %*
  exit /b
)
python -c "import sys; assert sys.version_info[:2] == (3,11)" >nul 2>nul
if not errorlevel 1 (
  python %*
  exit /b
)
echo Python 3.11 was not found. Install Python 3.11 and enable Add Python to PATH.
echo Download: https://www.python.org/downloads/
echo Or set TTS_PYTHON to the full path of Python 3.11.
exit /b 1
:custom
"%TTS_PYTHON%" %*
exit /b
