@echo off
title Toontown Ranked: Main Game Launcher
cd ..\..

REM Try to find Python in PATH first, then use PPYTHON_PATH if available
set PYTHON_CMD=python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=py
    ) else (
        REM Try to read PPYTHON_PATH if it exists
        if exist PPYTHON_PATH (
            set /P PYTHON_CMD=<PPYTHON_PATH
        ) else (
            echo Python not found in PATH and PPYTHON_PATH file not found.
            echo Please install Python 3.12+ and add it to your PATH.
            pause
            exit /b 1
        )
    )
)

REM Run dependency checker
echo Checking dependencies...
%PYTHON_CMD% -m launch.launcher.dependency_checker
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Dependency check failed. Please install missing dependencies and try again.
    pause
    exit /b 1
)

REM Now use PPYTHON_PATH if it exists, otherwise use the Python we found
if exist PPYTHON_PATH (
    set /P PPYTHON_PATH=<PPYTHON_PATH
) else (
    set PPYTHON_PATH=%PYTHON_CMD%
)

set SERVICE_TO_RUN=CLIENT

:main
    %PPYTHON_PATH% -m pip install -r requirements.txt
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto :main