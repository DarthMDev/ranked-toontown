@echo off
title Toontown Ranked - Client
set SERVICE_TO_RUN=CLIENT
cd game

:launch
start /B "%~dp0" "launch.exe"
pause
goto :launcher

pause