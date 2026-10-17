@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
call "%~dp0scripts\python.cmd" "%~dp0scripts\install_plugin.py" %*
set "TTS_EXIT=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %TTS_EXIT%
