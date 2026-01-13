@echo off
title Toontown Ranked: Astron Launcher
cd ../../..

REM Run pre-flight dependency checker (checks Python and MongoDB before running Python scripts)
call launch\windows\check_dependencies.bat
if %ERRORLEVEL% NEQ 0 (
    exit /b 1
)

REM Now that we know Python is available, find it
set PYTHON_CMD=python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=py
    ) else (
        echo Error: Python not found after dependency check.
        pause
        exit /b 1
    )
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
