@echo off
setlocal enabledelayedexpansion
title Toontown Ranked: Astron Launcher
cd ../../..

REM Try to find Python in PATH first, then use PPYTHON_PATH if available
set PYTHON_CMD=
set PYTHON_FOUND=0

REM Check if python command works (not just exists - Windows Store alias can exist but not work)
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
    set PYTHON_FOUND=1
) else (
    REM Try py launcher
    py --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=py
        set PYTHON_FOUND=1
    ) else (
        REM Try to read PPYTHON_PATH if it exists
        if exist launch/windows/PPYTHON_PATH (
            set /P PYTHON_CMD=<launch/windows/PPYTHON_PATH
            %PYTHON_CMD% --version >nul 2>&1
            if %ERRORLEVEL% EQU 0 (
                set PYTHON_FOUND=1
            )
        )
    )
)

REM If Python still not found, prompt for installation
if %PYTHON_FOUND% EQU 0 (
    echo ============================================================
    echo Python 3.12+ is required but not found.
    echo ============================================================
    echo.
    echo Python is mandatory to run Toontown Ranked.
    echo.
    set /p INSTALL_PYTHON="Would you like to install Python 3.12+ now? (y/n): "
    if /i "!INSTALL_PYTHON!"=="y" (
        echo.
        echo Attempting to install Python using winget...
        echo This may take a few minutes. Please wait...
        echo.
        winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        set WINGET_RESULT=%ERRORLEVEL%
        if %WINGET_RESULT% EQU 0 (
            echo.
            echo ============================================================
            echo Python installation completed successfully!
            echo ============================================================
            echo.
            echo IMPORTANT: You must close and reopen this terminal window
            echo for Python to be available in your PATH.
            echo.
            echo After restarting the terminal, run this script again.
            pause
            exit /b 0
        ) else (
            echo.
            echo ============================================================
            echo winget installation failed (Error code: %WINGET_RESULT%)
            echo ============================================================
            echo.
            echo This could mean:
            echo   - winget is not available on your system
            echo   - You need administrator privileges
            echo   - Network connection issues
            echo.
            echo Please try one of the following:
            echo   1. Run this script as Administrator
            echo   2. Install Python manually from: https://www.python.org/downloads/
            echo      (Make sure to check "Add Python to PATH" during installation)
            pause
            exit /b 1
        )
    ) else (
        echo.
        echo ============================================================
        echo Python installation is required to continue.
        echo ============================================================
        echo.
        echo You cannot run Toontown Ranked without Python 3.12+.
        echo.
        echo Please install Python from: https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
)

REM Run dependency checker (MongoDB required for Astron)
echo Checking dependencies...
set CALLED_FROM_LAUNCH_SCRIPT=1
%PYTHON_CMD% -m launch.launcher.dependency_checker --require-mongodb
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Dependency check failed. Please install missing dependencies and try again.
    pause
    exit /b 1
)

REM Now use PPYTHON_PATH if it exists, otherwise use the Python we found
if exist launch/windows/PPYTHON_PATH (
    set /P PPYTHON_PATH=<launch/windows/PPYTHON_PATH
) else (
    set PPYTHON_PATH=%PYTHON_CMD%
)

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    %PPYTHON_PATH% launch/launcher/start_astron.py
    pause
goto main
