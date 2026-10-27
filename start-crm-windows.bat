@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"

set "CRM_HOST=0.0.0.0"
set "CRM_PORT=8000"
set "LOCAL_URL=http://127.0.0.1:%CRM_PORT%"

echo %LOCAL_URL%
start "" "%LOCAL_URL%"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py
) else (
    python app.py
)

pause
popd
