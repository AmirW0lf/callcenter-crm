@echo off
chcp 65001 >nul
title CallCenter CRM - Push to GitHub

echo ========================================================
echo   CallCenter CRM - ارسال خودکار به گیت‌هاب (Push)
echo ========================================================
echo.
echo نمونه آدرس: https://github.com/your-username/callcenter-crm.git
echo.
set /p REPO_URL="لطفاً آدرس ریپازیتوری گیت‌هاب خود را وارد کنید: "

if "%REPO_URL%"=="" (
    echo [خطا] آدرسی وارد نشد.
    pause
    exit /b
)

echo.
echo در حال اتصال به ریموت و ارسال کدها...
cd /d "%~dp0.."
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo   [موفقیت] پروژه با موفقیت به گیت‌هاب ارسال گردید!
    echo ========================================================
) else (
    echo.
    echo [خطا] در صورت درخواست دسترسی گیت‌هاب، مرورگر را تأیید کنید یا از Personal Access Token استفاده نمایید.
)

echo.
pause
