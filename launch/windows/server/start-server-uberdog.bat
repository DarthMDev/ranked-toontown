@echo off
title Toontown Ranked: UD Launcher
cd ../../../

REM Try to find Python in PATH first, then use PPYTHON_PATH if available
set PYTHON_CMD=python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PYTHON_CMD=py
    ) else (
        REM Try to read PPYTHON_PATH if it exists
        if exist ../PPYTHON_PATH (
            set /P PYTHON_CMD=<../PPYTHON_PATH
        ) else (
            echo ============================================================
            echo Python 3.12+ is required but not found.
            echo ============================================================
            echo.
            echo Python is mandatory to run Toontown Ranked.
            echo.
            set /p INSTALL_PYTHON="Would you like to install Python 3.12+ now? (y/n): "
            if /i "%INSTALL_PYTHON%"=="y" (
                echo.
                echo Attempting to install Python using winget...
                winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
                if %ERRORLEVEL% EQU 0 (
                    echo.
                    echo Python installation completed!
                    echo Please restart this script after Python is added to your PATH.
                    echo You may need to close and reopen this terminal window.
                    pause
                    exit /b 0
                ) else (
                    echo.
                    echo winget installation failed. Trying alternative method...
                    echo Please visit https://www.python.org/downloads/ to install Python manually.
                    echo Make sure to check "Add Python to PATH" during installation.
                    pause
                    exit /b 1
                )
            ) else (
                echo.
                echo Python installation is required to continue.
                echo You cannot run Toontown Ranked without Python 3.12+.
                echo.
                echo Please install Python from: https://www.python.org/downloads/
                echo Make sure to check "Add Python to PATH" during installation.
                pause
                exit /b 1
            )
        )
    )
)

REM Run dependency checker (MongoDB required for server)
echo Checking dependencies...
set CALLED_FROM_LAUNCH_SCRIPT=1
%PYTHON_CMD% -m launch.launcher.dependency_checker --require-mongodb
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Dependency check failed. Please install missing dependencies and try again.
    pause
    exit /b 1
)

REM Now use PPYTHON_PATH if it exists, otherwise use the Python we found
if exist ../PPYTHON_PATH (
    set /P PPYTHON_PATH=<../PPYTHON_PATH
) else (
    set PPYTHON_PATH=%PYTHON_CMD%
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
    set CALLED_FROM_LAUNCH_SCRIPT=1
    %PPYTHON_PATH% -m launch.launcher.launch
    pause
goto main
