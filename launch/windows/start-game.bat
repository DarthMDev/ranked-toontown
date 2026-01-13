@echo off
title Toontown Ranked: Main Game Launcher
cd ..\..

REM Check for Python installation using PowerShell script (handles installation if needed)
echo Verifying Python installation...
powershell -ExecutionPolicy Bypass -File "launch\windows\check_python.ps1"
set PYTHON_CHECK_RESULT=%ERRORLEVEL%

if %PYTHON_CHECK_RESULT% EQU 2 (
    echo.
    echo Python was just installed. Please restart this launcher.
    pause
    exit /b 0
)

if %PYTHON_CHECK_RESULT% NEQ 0 (
    echo.
    echo Python check failed. Please install Python and try again.
    pause
    exit /b 1
)

REM Read the Python command from PPYTHON_PATH (created by PowerShell script)
if exist launch\windows\PPYTHON_PATH (
    set /P PYTHON_CMD=<launch\windows\PPYTHON_PATH
) else (
    echo Error: PPYTHON_PATH not found after successful Python check.
    echo Falling back to 'python' command...
    set PYTHON_CMD=python
)

REM Run dependency checker
echo Checking dependencies...
set CALLED_FROM_LAUNCH_SCRIPT=1
%PYTHON_CMD% -m launch.launcher.dependency_checker
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Dependency check failed. Please install missing dependencies and try again.
    pause
    exit /b 1
)

REM Use the Python command we found
set PPYTHON_PATH=%PYTHON_CMD%

set SERVICE_TO_RUN=CLIENT

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    set CALLED_FROM_LAUNCH_SCRIPT=1
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto :main