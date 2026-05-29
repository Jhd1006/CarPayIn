@echo off
setlocal

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-local-e2e.ps1" %*
exit /b %ERRORLEVEL%
