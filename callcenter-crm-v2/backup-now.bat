@echo off
chcp 65001 >nul
title CallCenter CRM - Instant Backup

set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_CMD if exist "C:\Python313\python.exe" set "PY_CMD=C:\Python313\python.exe"
if not defined PY_CMD if exist "C:\Python312\python.exe" set "PY_CMD=C:\Python312\python.exe"
if not defined PY_CMD set "PY_CMD=python"

echo ========================================================
echo   CallCenter CRM - اجرای پشتیبان‌گیری پایگاه داده
echo ========================================================
cd /d "%~dp0"
"%PY_CMD%" backup_manager.py
echo.
pause
