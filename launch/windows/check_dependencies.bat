@echo off
REM Pre-flight dependency checker for Windows
REM Checks for Python and MongoDB before running the Python dependency checker
REM This is needed because we can't run Python scripts if Python isn't installed!

setlocal enabledelayedexpansion

set PYTHON_FOUND=0
set PYTHON_VERSION_OK=0
set MONGODB_FOUND=0
set MONGODB_RUNNING=0

echo ========================================
echo Toontown Ranked - Dependency Checker
echo ========================================
echo.

REM Check for Python
echo Checking Python installation...
set PYTHON_CMD=
set PYTHON_VERSION=
set PYTHON_FOUND=0

REM Use 'py' launcher (Windows Python launcher)
REM Capture output and check for actual version number (not Windows Store stub message)
set PYTHON_VERSION_RAW=
for /f "delims=" %%v in ('py --version 2^>^&1') do set PYTHON_VERSION_RAW=%%v

REM Check if this is the Windows Store stub message
echo !PYTHON_VERSION_RAW! | findstr /i "Microsoft Store" >nul
if %ERRORLEVEL% EQU 0 (
    REM This is the Windows Store stub, not real Python
    set PYTHON_FOUND=0
) else (
    REM Check if output contains a version number pattern
    echo !PYTHON_VERSION_RAW! | findstr /r "[0-9]\.[0-9]" >nul
    if %ERRORLEVEL% EQU 0 (
        REM Extract version - handle both "Python 3.12.1" and "3.12.1" formats
        for /f "tokens=1,2" %%a in ("!PYTHON_VERSION_RAW!") do (
            if /i "%%a"=="Python" (
                set PYTHON_VERSION=%%b
            ) else (
                REM Check if first token is a version number
                echo %%a | findstr /r "^[0-9]\.[0-9]" >nul
                if %ERRORLEVEL% EQU 0 (
                    set PYTHON_VERSION=%%a
                )
            )
        )
        REM Verify we got a valid version string (must start with digit)
        if not "!PYTHON_VERSION!"=="" (
            echo !PYTHON_VERSION! | findstr /r "^[0-9]" >nul
            if %ERRORLEVEL% EQU 0 (
                set PYTHON_CMD=py
                set PYTHON_FOUND=1
            )
        )
    )
)

if !PYTHON_FOUND! EQU 1 (
    if not "!PYTHON_VERSION!"=="" (
        echo Found Python: !PYTHON_VERSION!
        
        REM Extract version numbers - handle formats like "Python 3.12.1" or "3.12.1"
        REM Remove "Python " prefix if present
        set CLEAN_VERSION=!PYTHON_VERSION:Python =!
        
        REM Extract major and minor version
        for /f "tokens=1,2 delims=." %%a in ("!CLEAN_VERSION!") do (
            set MAJOR=%%a
            set MINOR=%%b
        )
        
        REM Check if version is 3.12 or higher
        if !MAJOR! GTR 3 (
            set PYTHON_VERSION_OK=1
        ) else if !MAJOR! EQU 3 (
            if !MINOR! GEQ 12 (
                set PYTHON_VERSION_OK=1
            )
        )
        
        if !PYTHON_VERSION_OK! EQU 1 (
            echo [OK] Python version is compatible (3.12+)
        ) else (
            echo [ERROR] Python version is too old: !PYTHON_VERSION! (requires 3.12+)
        )
    ) else (
        echo [ERROR] Python found but version could not be determined
        set PYTHON_FOUND=0
    )
)

if !PYTHON_FOUND! EQU 0 (
    echo [ERROR] Python not found
)

echo.

REM Check for MongoDB (only if Python is available, otherwise we'll check after Python is installed)
if %PYTHON_FOUND% EQU 1 (
    echo Checking MongoDB installation...
    mongod --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set MONGODB_FOUND=1
        echo [OK] MongoDB is installed
        
        REM Check if MongoDB is running (only if Python is available)
        echo Checking if MongoDB is running...
        %PYTHON_CMD% -c "from pymongo import MongoClient; from pymongo.errors import ServerSelectionTimeoutError; client = MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=2000); client.admin.command('ping'); client.close()" >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            set MONGODB_RUNNING=1
            echo [OK] MongoDB is running
        ) else (
            echo [WARNING] MongoDB is installed but not running
            echo   Please start MongoDB service or run: net start MongoDB
        )
    ) else (
        echo [ERROR] MongoDB not found
    )
) else (
    echo Skipping MongoDB check (Python required for MongoDB connection test)
    echo MongoDB will be checked after Python is installed.
)

echo.

REM If Python is missing or outdated, prompt for installation
if %PYTHON_FOUND% EQU 0 (
    echo Python is required but not installed.
    set /p INSTALL_PYTHON="Would you like to install Python? (y/n): "
    if /i "!INSTALL_PYTHON!"=="y" (
        echo Installing latest Python using winget...
        winget install Python.Python --silent --accept-package-agreements --accept-source-agreements
        if %ERRORLEVEL% EQU 0 (
            echo.
            echo Python installation completed. Please restart your terminal and try again.
            pause
            exit /b 1
        ) else (
            echo.
            echo Python installation failed. Please install Python manually from https://www.python.org/downloads/
            pause
            exit /b 1
        )
    ) else (
        echo.
        echo Python installation is required to continue.
        pause
        exit /b 1
    )
) else if %PYTHON_VERSION_OK% EQU 0 (
    echo Python version is too old. An upgrade is required.
    set /p UPGRADE_PYTHON="Would you like to upgrade Python to the latest version? (y/n): "
    if /i "!UPGRADE_PYTHON!"=="y" (
        echo Upgrading Python to latest version using winget...
        winget upgrade Python.Python --silent --accept-package-agreements --accept-source-agreements
        if %ERRORLEVEL% EQU 0 (
            echo.
            echo Python upgrade completed. Please restart your terminal and try again.
            pause
            exit /b 1
        ) else (
            echo.
            echo Python upgrade failed. Please upgrade Python manually from https://www.python.org/downloads/
            pause
            exit /b 1
        )
    ) else (
        echo.
        echo Python upgrade is required to continue.
        pause
        exit /b 1
    )
)

REM If MongoDB is missing, prompt for installation (only if Python is now available)
if %PYTHON_FOUND% EQU 1 (
    if %MONGODB_FOUND% EQU 0 (
        echo MongoDB is required but not installed.
        set /p INSTALL_MONGODB="Would you like to install MongoDB? (y/n): "
        if /i "!INSTALL_MONGODB!"=="y" (
            echo Installing MongoDB using winget...
            winget install MongoDB.Server --silent --accept-package-agreements --accept-source-agreements
            if %ERRORLEVEL% EQU 0 (
                echo.
                echo MongoDB installation completed.
                echo IMPORTANT: Please restart your terminal and start MongoDB service.
                echo You can start MongoDB with: net start MongoDB
                pause
                exit /b 1
            ) else (
                echo.
                echo MongoDB installation failed. Please install MongoDB manually from https://www.mongodb.com/try/download/community
                pause
                exit /b 1
            )
        ) else (
            echo.
            echo MongoDB installation is required to continue.
            pause
            exit /b 1
        )
    ) else if %MONGODB_RUNNING% EQU 0 (
        echo MongoDB is installed but not running.
        echo Please start MongoDB service or run: net start MongoDB
        echo.
        set /p START_MONGODB="Would you like to start MongoDB service now? (y/n): "
        if /i "!START_MONGODB!"=="y" (
            net start MongoDB
            if %ERRORLEVEL% NEQ 0 (
                echo Failed to start MongoDB service. Please start it manually.
                pause
                exit /b 1
            )
        ) else (
            echo.
            echo MongoDB must be running to continue.
            pause
            exit /b 1
        )
    )
)

REM All dependencies are satisfied
echo.
echo [OK] All dependencies are satisfied!
echo.
endlocal
exit /b 0
