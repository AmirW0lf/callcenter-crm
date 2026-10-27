@echo off
chcp 65001 >nul
title CallCenter CRM - تنظیم پشتیبان‌گیری خودکار شبانه در ویندوز

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_CMD if exist "C:\Python313\python.exe" set "PY_CMD=C:\Python313\python.exe"
if not defined PY_CMD set "PY_CMD=python"

set "TASK_NAME=CallCenterCRM_Nightly_Backup"
set "SCRIPT_PATH=%~dp0backup_manager.py"
set "CMD_TO_RUN=\"%PY_CMD%\" \"%SCRIPT_PATH%\""

echo ========================================================
echo   CallCenter CRM - تنظیم Task Scheduler ویندوز
echo   زمان اجرای پیش‌فرض: هر شب ساعت 02:00 بامداد
echo ========================================================
echo.

schtasks /Create /SC DAILY /TN "%TASK_NAME%" /TR "%CMD_TO_RUN%" /ST 02:00 /F

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] تسک با موفقیت در ویندوز ثبت شد!
    echo نام تسک: %TASK_NAME%
    echo زمان اجرا: هر شب ساعت 02:00
    echo نسخه پشتیبان در پوشه backups ذخیره خواهد شد.
) else (
    echo.
    echo [ERROR] خطا در ثبت تسک. لطفا فایل را با راست‌کلیک و Run as Administrator اجرا کنید.
)

echo.
pause
