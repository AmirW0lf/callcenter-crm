@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
pushd "%~dp0"

set "CRM_HOST=0.0.0.0"
set "CRM_PORT=8000"
set "LOCAL_URL=http://127.0.0.1:%CRM_PORT%"

echo ========================================================
echo    Starting CallCenter CRM v2.0 (Multilingual)
echo    Opening browser at %LOCAL_URL%
echo ========================================================

start "" "%LOCAL_URL%"

:: 1. Try python in PATH
where python >nul 2>nul
if not errorlevel 1 (
    python app.py
    goto done
)

:: 2. Try py launcher
where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py
    if not errorlevel 1 goto done
)

:: 3. Check standard User AppData Python paths
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" app.py
        goto done
    )
)

:: 4. Check Program Files
for /d %%D in ("%ProgramFiles%\Python*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" app.py
        goto done
    )
)

echo [ERROR] Python not found! Please install Python 3.9+ or run using an installed Python.
pause

:done
popd
