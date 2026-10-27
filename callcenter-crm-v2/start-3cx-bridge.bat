@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"

set "BRIDGE_HOST=0.0.0.0"
set "BRIDGE_PORT=8090"
set "BRIDGE_TZ_OFFSET_HOURS=3.5"
rem set "BRIDGE_TOKEN=CHANGE_ME"
rem set "BRIDGE_AGENT_MAP=101=2,102=3"
rem set "BRIDGE_CRM_DB=%~dp0crm.sqlite3"

if exist "%~dp03cx_bridge.exe" (
    echo 3CX bridge starting (standalone exe) on http://0.0.0.0:%BRIDGE_PORT%/3cx/webhook
    echo Press Ctrl+C to stop.
    "%~dp03cx_bridge.exe"
    pause
    popd
    exit /b 0
)

where py >nul 2>nul
if errorlevel 1 (set "PY=python") else (set "PY=py -3")
echo 3CX bridge starting (python) on http://0.0.0.0:%BRIDGE_PORT%/3cx/webhook
echo Press Ctrl+C to stop.
%PY% 3cx_bridge.py
pause
popd
