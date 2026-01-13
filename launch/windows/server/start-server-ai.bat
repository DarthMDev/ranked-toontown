@echo off
title Toontown Ranked: AI Launcher
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
if exist ../PPYTHON_PATH (
    set /P PPYTHON_PATH=<../PPYTHON_PATH
) else (
    set PPYTHON_PATH=%PYTHON_CMD%
)

set SERVICE_TO_RUN=AI
set BASE_CHANNEL=401000000
set MAX_CHANNELS=999999
set STATESERVER=4002
set DISTRICT_NAME=Ranked Realms
set ASTRON_IP=127.0.0.1:7199
set EVENTLOGGER_IP=127.0.0.1:7197
set WANT_ERROR_REPORTING=true

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    set CALLED_FROM_LAUNCH_SCRIPT=1
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto main
