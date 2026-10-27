@echo off
chcp 65001 >nul
title CallCenter CRM - حذف تسک پشتیبان‌گیری خودکار

set "TASK_NAME=CallCenterCRM_Nightly_Backup"

echo ========================================================
echo   CallCenter CRM - حذف تسک %TASK_NAME% از Task Scheduler
echo ========================================================
echo.

schtasks /Delete /TN "%TASK_NAME%" /F

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] تسک با موفقیت حذف گردید.
) else (
    echo.
    echo [INFO] تسک پیدا نشد یا قبلاً حذف شده است.
)

echo.
pause
