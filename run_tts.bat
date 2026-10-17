@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup.ps1 first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" tts.py --play %*
if errorlevel 1 pause
