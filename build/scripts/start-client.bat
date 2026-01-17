@echo off
title Toontown Ranked - Client
set SERVICE_TO_RUN=CLIENT
cd game

:launch
start /B /WAIT "%~dp0" "launch.exe"
echo.
echo Game closed. Press Enter to relaunch, or Ctrl+C to exit...
pause >nul
goto :launch