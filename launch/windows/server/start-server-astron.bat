@echo off
title Toontown Ranked: Astron Launcher
cd ../../..

REM Check for dependencies using PowerShell script (Python + MongoDB)
echo Checking dependencies...
powershell -ExecutionPolicy Bypass -File "launch\windows\check_dependencies.ps1"
set DEPENDENCY_CHECK_RESULT=%ERRORLEVEL%

if %DEPENDENCY_CHECK_RESULT% EQU 2 (
    echo.
    echo Dependencies were just installed. Please restart this launcher.
    pause
    exit /b 0
)

if %DEPENDENCY_CHECK_RESULT% NEQ 0 (
    echo.
    echo Dependency check failed. Please install missing dependencies and try again.
    pause
    exit /b 1
)

REM Read the Python command from PPYTHON_PATH (created by PowerShell script)
if exist launch\windows\PPYTHON_PATH (
    set /P PYTHON_CMD=<launch\windows\PPYTHON_PATH
) else (
    echo Error: PPYTHON_PATH not found after successful dependency check.
    echo Falling back to 'python' command...
    set PYTHON_CMD=python
)

REM Use the Python command we found
set PPYTHON_PATH=%PYTHON_CMD%

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    %PPYTHON_PATH% launch/launcher/start_astron.py
    pause
goto main
