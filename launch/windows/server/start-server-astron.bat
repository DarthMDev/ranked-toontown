@echo off
title Toontown Ranked: Astron Launcher
cd ../../..

REM Read PPYTHON_PATH from file
if exist launch\windows\PPYTHON_PATH (
    set /P PPYTHON_PATH=<launch\windows\PPYTHON_PATH
) else (
    echo Error: PPYTHON_PATH file not found at launch\windows\PPYTHON_PATH
    pause
    exit /b 1
)

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    %PPYTHON_PATH% launch/launcher/start_astron.py
    pause
goto main
