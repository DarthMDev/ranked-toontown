@echo off
title Toontown Ranked: UD Launcher
cd ../../../

REM Read PPYTHON_PATH from file
if exist launch\windows\PPYTHON_PATH (
    set /P PPYTHON_PATH=<launch\windows\PPYTHON_PATH
) else (
    echo Error: PPYTHON_PATH file not found at launch\windows\PPYTHON_PATH
    pause
    exit /b 1
)

set SERVICE_TO_RUN=UD
set BASE_CHANNEL=1000000
set MAX_CHANNELS=999999
set STATESERVER=4002
set ASTRON_IP=127.0.0.1:7199
set EVENTLOGGER_IP=127.0.0.1:7197
set WANT_ERROR_REPORTING=true

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    echo Checking for valid Panda3D Windows installation...
    %PPYTHON_PATH% -m pip install "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-win_amd64.whl"
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto main
