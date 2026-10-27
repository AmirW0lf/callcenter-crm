@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"

set "CRM_HOST=0.0.0.0"
set "CRM_PORT=8000"
set "LOCAL_URL=http://127.0.0.1:%CRM_PORT%"

echo %LOCAL_URL%
start "" "%LOCAL_URL%"

if not exist "CallCenterCRM.exe" (
    echo فایل CallCenterCRM.exe پیدا نشد.
    pause
    exit /b 1
)

CallCenterCRM.exe
pause
popd
