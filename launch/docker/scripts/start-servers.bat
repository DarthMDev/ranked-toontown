@echo off
title Toontown Ranked: Docker Server Launcher
cd /d "%~dp0\.."

echo ========================================
echo   Toontown Ranked - Server Launcher
echo ========================================
echo.

REM Check if Docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker is not installed or not in PATH
    echo Please run initial-setup.bat first to install dependencies
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Docker is not running. Attempting to start Docker Desktop...
    echo.
    
    REM Try common Docker Desktop installation paths
    set DOCKER_STARTED=0
    
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        set DOCKER_STARTED=1
    ) else if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe" (
        start "" "%LOCALAPPDATA%\Docker\Docker Desktop.exe"
        set DOCKER_STARTED=1
    ) else if exist "%ProgramFiles(x86)%\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles(x86)%\Docker\Docker Desktop.exe"
        set DOCKER_STARTED=1
    )
    
    if %DOCKER_STARTED% equ 1 (
        echo Waiting for Docker to start (this may take 30-60 seconds)...
        echo Please wait...
        
        REM Wait up to 60 seconds for Docker to be ready
        set TIMEOUT=60
        set ELAPSED=0
        :wait_loop
        timeout /t 2 /nobreak >nul
        set /a ELAPSED+=2
        docker info >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            echo Docker is now running!
            echo.
            goto docker_ready
        )
        if %ELAPSED% lss %TIMEOUT% (
            goto wait_loop
        )
        
        echo.
        echo WARNING: Docker Desktop is starting but may not be ready yet.
        echo Please wait a moment and try running this script again.
        echo.
        pause
        exit /b 1
    ) else (
        echo ERROR: Could not find Docker Desktop installation.
        echo Please start Docker Desktop manually and try again.
        echo.
        echo Common locations:
        echo   - C:\Program Files\Docker\Docker\Docker Desktop.exe
        echo   - %LOCALAPPDATA%\Docker\Docker Desktop.exe
        pause
        exit /b 1
    )
    
    :docker_ready
)

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found
    if exist "env.example" (
        echo Creating .env from env.example...
        copy env.example .env
        echo Please edit .env with your configuration
        pause
    ) else (
        echo ERROR: env.example not found
        pause
        exit /b 1
    )
)

echo Starting Toontown Ranked servers in Docker...
echo This may take a few minutes on first run...
echo.

docker compose up -d

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo   Servers started successfully!
    echo ========================================
    echo.
    echo Services running:
    docker compose ps
    echo.
    echo To view logs: docker compose logs -f
    echo To stop servers: docker compose down
    echo.
) else (
    echo.
    echo ERROR: Failed to start servers
    echo Check the error messages above
    pause
    exit /b 1
)

pause
