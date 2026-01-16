@echo off
title Toontown Ranked: Game Client Launcher
cd /d "%~dp0\..\..\..\"

echo ========================================
echo   Toontown Ranked - Client Launcher
echo ========================================
echo.

REM Read PPYTHON_PATH from file
if exist launch\windows\PPYTHON_PATH (
    set /P PPYTHON_PATH=<launch\windows\PPYTHON_PATH
) else (
    REM Try to find Python 3.11
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        python --version | findstr "3.11" >nul
        if %ERRORLEVEL% equ 0 (
            set PPYTHON_PATH=python
        ) else (
            echo ERROR: Python 3.11 not found
            echo Please run initial-setup.bat first to install dependencies
            pause
            exit /b 1
        )
    ) else (
        echo ERROR: Python not found
        echo Please run initial-setup.bat first to install dependencies
        pause
        exit /b 1
    )
)

set SERVICE_TO_RUN=CLIENT

echo Installing Python dependencies...
%PPYTHON_PATH% -m pip install -r requirements.txt --quiet

echo Checking for valid Panda3D Windows installation...
%PPYTHON_PATH% -m pip install "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-win_amd64.whl" --quiet

echo.
echo Starting Toontown Ranked client...
echo.

%PPYTHON_PATH% -m launch.launcher.launch

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to start game client
    pause
    exit /b 1
)
