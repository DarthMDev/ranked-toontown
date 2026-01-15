@echo off
title Toontown Ranked: Main Game Launcher
cd ..\..

REM Read PPYTHON_PATH from file
if exist launch\windows\PPYTHON_PATH (
    set /P PPYTHON_PATH=<launch\windows\PPYTHON_PATH
) else (
    echo Error: PPYTHON_PATH file not found at launch\windows\PPYTHON_PATH
    pause
    exit /b 1
)

set SERVICE_TO_RUN=CLIENT

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    set CALLED_FROM_LAUNCH_SCRIPT=1
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto :main