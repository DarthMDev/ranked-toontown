@echo off
title Toontown Ranked: Stop Docker Servers
cd /d "%~dp0\.."

echo ========================================
echo   Toontown Ranked - Stop Servers
echo ========================================
echo.

docker compose down

if %ERRORLEVEL% equ 0 (
    echo.
    echo Servers stopped successfully!
    echo.
) else (
    echo.
    echo ERROR: Failed to stop servers
    pause
    exit /b 1
)

pause
