@echo off
title Toontown Ranked: Dedicated Server
set /P PPYTHON_PATH=<../PPYTHON_PATH
cd ../../../


:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    %PPYTHON_PATH% -m toontown.toonbase.DedicatedServerStart
    pause
goto main
