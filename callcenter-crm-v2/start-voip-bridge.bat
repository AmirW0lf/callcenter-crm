@echo off
chcp 65001 >nul
title CallCenter CRM - VoIP & 3CX / Asterisk Bridge

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_CMD if exist "C:\Python313\python.exe" set "PY_CMD=C:\Python313\python.exe"
if not defined PY_CMD if exist "C:\Python312\python.exe" set "PY_CMD=C:\Python312\python.exe"
if not defined PY_CMD set "PY_CMD=python"

echo ========================================================
echo   CallCenter CRM - بریج اتصال سانترال تلفنی (3CX / Asterisk)
echo ========================================================
echo.
echo گزینه مورد نظر را انتخاب کنید:
echo 1) اجرای بریج 3CX روی پورت 5000
echo 2) اجرای بریج Asterisk / Issabel (AMI)
echo 3) اجرای شبیه‌ساز تماس ورودی تستی (Screen-Pop Test)
echo.
set /p opt="انتخاب شما (1-3): "

if "%opt%"=="2" (
    "%PY_CMD%" voip_bridge.py --mode asterisk
) else if "%opt%"=="3" (
    "%PY_CMD%" voip_bridge.py --simulate
    pause
) else (
    "%PY_CMD%" voip_bridge.py --mode 3cx
)
