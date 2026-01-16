@echo off
title Toontown Ranked: Main Game Launcher
set /P PPYTHON_PATH=<PPYTHON_PATH
set SERVICE_TO_RUN=CLIENT
cd ..\..

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    %PPYTHON_PATH% -m pip install -r "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-win_amd64.whl"
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto :main