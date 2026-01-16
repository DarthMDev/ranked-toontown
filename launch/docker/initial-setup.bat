@echo off
title Toontown Ranked: Installation Wizard
setlocal enabledelayedexpansion

REM Check for help flag
if "%1"=="--help" goto :show_help
if "%1"=="-h" goto :show_help

REM Check for administrator privileges
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo This script requires administrator privileges.
    echo Requesting elevation...
    echo.
    REM Re-launch with administrator privileges
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM Change to script directory
cd /d "%~dp0"

echo ========================================
echo   Toontown Ranked - Installation Wizard
echo ========================================
echo.
goto :start_checks

:show_help
echo Toontown Ranked - Installation Wizard
echo.
echo This script checks and installs required dependencies:
echo   - Python 3.11
echo   - Git
echo   - Docker
echo   - WSL2 (Windows only - checked but not required to install manually)
echo.
echo Usage: %~nx0 [--help]
echo.
exit /b 0

:start_checks

REM Check if winget is available
where winget >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: winget is not available.
    echo.
    echo winget is required for automatic installation.
    echo Please install Windows Package Manager or install dependencies manually.
    echo.
    echo Manual installation links:
    echo   Python 3.11: https://www.python.org/downloads/
    echo   Git: https://git-scm.com/download/win
    echo   Docker: https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

echo Checking dependencies...
echo.

set MISSING_COUNT=0
set INSTALL_LIST=
set WSL_NEEDS_UPGRADE=0

REM First check hardware virtualization - this is critical for WSL2 and Docker
set HARDWARE_VIRT_OK=1
call :check_hardware_virtualization
REM Note: We don't exit if virtualization check fails, WSL/Docker will fail later if it's actually disabled

REM Function to check Python 3.11
call :check_python_311
goto :check_git

:check_python_311
set PYTHON_FOUND=0
set PYTHON_TEMP_FILE=temp_python_check_%RANDOM%.txt

REM First try python --version (simpler and more reliable)
python --version >!PYTHON_TEMP_FILE! 2>&1
timeout /t 2 /nobreak >nul
REM Check if we got "Python 3.11" in the output
findstr /R "Python 3\.11" !PYTHON_TEMP_FILE! >nul
if !ERRORLEVEL! equ 0 (
    REM Check that it doesn't contain store-related text (Microsoft Store stub)
    findstr /I /C:"was not found" /C:"run without arguments" /C:"microsoft store" /C:"app execution aliases" !PYTHON_TEMP_FILE! >nul
    if !ERRORLEVEL! neq 0 (
        REM No store text found, it's real Python 3.11
        set PYTHON_FOUND=1
    )
)

REM If simple check didn't work, try the more complex check
if !PYTHON_FOUND! equ 0 (
    set PYTHON_TEMP_FILE2=temp_python_check2_%RANDOM%.txt
    python -c "import sys; print('PYTHON_VERSION:', sys.version_info.major, sys.version_info.minor)" >!PYTHON_TEMP_FILE2! 2>&1
    timeout /t 2 /nobreak >nul
    findstr /R "PYTHON_VERSION: 3 11" !PYTHON_TEMP_FILE2! >nul
    if !ERRORLEVEL! equ 0 (
        REM Check for store text
        findstr /I /C:"was not found" /C:"run without arguments" /C:"microsoft store" /C:"app execution aliases" !PYTHON_TEMP_FILE2! >nul
        if !ERRORLEVEL! neq 0 (
            set PYTHON_FOUND=1
        )
    )
    del !PYTHON_TEMP_FILE2! >nul 2>&1
)

REM Report results
if !PYTHON_FOUND! equ 1 (
    echo [X] Python 3.11 - INSTALLED
) else (
    REM Check if it's a different Python version
    findstr /R "Python 3\." !PYTHON_TEMP_FILE! >nul
    if !ERRORLEVEL! equ 0 (
        REM Different Python version found
        set /a MISSING_COUNT+=1
        set INSTALL_LIST=!INSTALL_LIST! Python
        echo [ ] Python 3.11 - WRONG VERSION
        type !PYTHON_TEMP_FILE!
    ) else (
        REM Check if it's the Microsoft Store stub
        findstr /I /C:"was not found" /C:"run without arguments" /C:"microsoft store" /C:"app execution aliases" !PYTHON_TEMP_FILE! >nul
        if !ERRORLEVEL! equ 0 (
            REM Microsoft Store stub detected
            set /a MISSING_COUNT+=1
            set INSTALL_LIST=!INSTALL_LIST! Python
            echo [ ] Python 3.11 - NOT INSTALLED
        ) else (
            REM Unknown - assume not installed
            set /a MISSING_COUNT+=1
            set INSTALL_LIST=!INSTALL_LIST! Python
            echo [ ] Python 3.11 - NOT INSTALLED
        )
    )
)
del !PYTHON_TEMP_FILE! >nul 2>&1
exit /b

:check_wsl
set WSL_FOUND=0
set WSL_NEEDS_UPGRADE=0
set WSL_TEMP_FILE=temp_wsl_check_%RANDOM%.txt
set WSL_VMP_TEMP_FILE=temp_wsl_vmp_%RANDOM%.txt
set WSL_STATUS_TEMP=temp_wsl_status_%RANDOM%.txt

REM Check if wsl.exe is available
where wsl >nul 2>nul
if !ERRORLEVEL! neq 0 (
    echo [~] WSL - NOT INSTALLED
    echo     WSL2 is required for Docker Desktop
    set WSL_NEEDS_UPGRADE=1
    goto :wsl_check_done
)

REM Check if WSL feature is enabled using DISM (fast check)
dism /online /get-featureinfo /featurename:Microsoft-Windows-Subsystem-Linux >!WSL_TEMP_FILE! 2>&1
findstr /I "Enabled" !WSL_TEMP_FILE! >nul
if !ERRORLEVEL! neq 0 (
    echo [~] WSL - NOT ENABLED
    echo     WSL2 is required for Docker Desktop
    set WSL_NEEDS_UPGRADE=1
    goto :wsl_check_done
)

REM Check if Virtual Machine Platform is enabled (required for WSL2)
dism /online /get-featureinfo /featurename:VirtualMachinePlatform >!WSL_VMP_TEMP_FILE! 2>&1
findstr /I "Enabled" !WSL_VMP_TEMP_FILE! >nul
if !ERRORLEVEL! neq 0 (
    echo [~] WSL - PARTIALLY INSTALLED
    echo     Virtual Machine Platform feature needs to be enabled
    set WSL_NEEDS_UPGRADE=1
    goto :wsl_check_done
)

REM Both features are enabled, now verify WSL is actually functional
REM Try wsl --status but capture output completely to prevent console leakage
set WSL_STATUS_FILE=temp_wsl_status_%RANDOM%.txt
wsl --status >!WSL_STATUS_FILE! 2>&1
timeout /t 1 /nobreak >nul 2>&1

REM Check the captured output
if exist !WSL_STATUS_FILE! (
    REM Check if it shows an update prompt (means WSL needs updating)
    findstr /I "update\|Update\|must be updated" !WSL_STATUS_FILE! >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        REM WSL needs update - features enabled but not fully ready
        echo [~] WSL2 - NEEDS UPDATE
        set WSL_NEEDS_UPGRADE=1
    ) else (
        REM Check if it shows WSL version 2 or appears functional
        findstr /I "WSL version: 2\|Default Version: 2" !WSL_STATUS_FILE! >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            echo [X] WSL2 - INSTALLED
        ) else (
            REM Features enabled, status unclear - assume needs configuration
            echo [~] WSL2 - FEATURES ENABLED
            set WSL_NEEDS_UPGRADE=1
        )
    )
    del !WSL_STATUS_FILE! >nul 2>&1
) else (
    REM Couldn't check status, assume features enabled but needs configuration
    echo [~] WSL2 - FEATURES ENABLED
    set WSL_NEEDS_UPGRADE=1
)

:wsl_check_done
del !WSL_TEMP_FILE! >nul 2>&1
del !WSL_VMP_TEMP_FILE! >nul 2>&1
del !WSL_STATUS_TEMP! >nul 2>&1
exit /b

:check_git

REM Check Git
where git >nul 2>nul
if !ERRORLEVEL! neq 0 (
    set /a MISSING_COUNT+=1
    set INSTALL_LIST=!INSTALL_LIST! Git
    echo [ ] Git - NOT INSTALLED
) else (
    echo [X] Git - INSTALLED
)

REM Check Docker (fast check to prevent hanging)
where docker >nul 2>nul
if !ERRORLEVEL! neq 0 (
    set /a MISSING_COUNT+=1
    set INSTALL_LIST=!INSTALL_LIST! Docker
    echo [ ] Docker - NOT INSTALLED
) else (
    REM Quick check if Docker Desktop process is running (fast, no hang)
    REM Check for both possible process names
    tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>nul | find /I "Docker Desktop.exe" >nul
    if !ERRORLEVEL! neq 0 (
        tasklist /FI "IMAGENAME eq com.docker.backend.exe" 2>nul | find /I "com.docker.backend.exe" >nul
    )
    if !ERRORLEVEL! equ 0 (
        echo [X] Docker - INSTALLED AND RUNNING
    ) else (
        echo [~] Docker - INSTALLED BUT NOT RUNNING
        echo     Please start Docker Desktop from the Start menu
    )
)

REM Check WSL (required for Docker Desktop on Windows)
call :check_wsl

echo.

REM If Docker is installed but WSL2 isn't properly configured, offer to fix it
where docker >nul 2>nul
if !ERRORLEVEL! equ 0 (
    if !WSL_NEEDS_UPGRADE! equ 1 (
        echo ========================================
        echo   WSL2 Configuration Required
        echo ========================================
        echo.
        echo Docker Desktop requires WSL2 to run properly on Windows.
        echo WSL2 is not currently configured correctly.
        echo.
        echo Would you like to install/configure WSL2 now?
        echo.
        choice /C YN /M "Configure WSL2"
        if errorlevel 2 goto :skip_wsl_check
        if errorlevel 1 (
            call :install_wsl2_now
        )
        :skip_wsl_check
        echo.
    )
)

if !MISSING_COUNT! equ 0 (
    echo All dependencies are installed!
    echo.
    echo Setup complete! You can now start the game.
    echo.
    echo Next steps:
    echo   1. Start servers: cd scripts ^&^& start-servers.bat
    echo   2. Start game client: cd scripts ^&^& start-game.bat
    echo.
    goto :end
)

echo ========================================
echo   Missing Dependencies Found
echo ========================================
echo.
echo Missing: !INSTALL_LIST!
echo.
echo Would you like to install missing dependencies automatically?
echo.
choice /C YN /M "Install now"
if errorlevel 2 goto :manual_install
if errorlevel 1 goto :auto_install

:auto_install
echo.
echo Installing missing dependencies...
echo This may take several minutes...
echo.

REM Install Python 3.11 - check if it's actually installed and is 3.11
set PYTHON_CHECK_TEMP=temp_python_check_%RANDOM%.txt
python -c "import sys; print('PYTHON_VERSION:', sys.version_info.major, sys.version_info.minor)" >!PYTHON_CHECK_TEMP! 2>&1
timeout /t 2 /nobreak >nul
findstr /R "PYTHON_VERSION: 3 11" !PYTHON_CHECK_TEMP! >nul
if !ERRORLEVEL! neq 0 (
    echo Installing Python 3.11...
    set WINGET_PYTHON_TEMP=temp_winget_python_%RANDOM%.txt
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements >!WINGET_PYTHON_TEMP! 2>&1
    set WINGET_EXIT=!ERRORLEVEL!
    REM Check output for success messages (winget may return non-zero even on success in some cases)
    findstr /I /C:"successfully installed" /C:"already installed" /C:"is already installed" /C:"installed" !WINGET_PYTHON_TEMP! >nul
    set OUTPUT_CHECK=!ERRORLEVEL!
    if !OUTPUT_CHECK! equ 0 (
        echo Python 3.11 installed successfully!
    ) else (
        if !WINGET_EXIT! equ 0 (
            REM Exit code was 0, assume success
            echo Python 3.11 installed successfully!
        ) else (
            echo WARNING: Failed to install Python 3.11 automatically
            type !WINGET_PYTHON_TEMP!
        )
    )
    del !WINGET_PYTHON_TEMP! >nul 2>&1
    echo.
)
del !PYTHON_CHECK_TEMP! >nul 2>&1

REM Install Git
where git >nul 2>nul
if !ERRORLEVEL! neq 0 (
    echo Installing Git...
    set WINGET_GIT_TEMP=temp_winget_git_%RANDOM%.txt
    winget install Git.Git --silent --accept-package-agreements --accept-source-agreements >!WINGET_GIT_TEMP! 2>&1
    set WINGET_EXIT=!ERRORLEVEL!
    REM Check output for success messages (winget may return non-zero even on success in some cases)
    findstr /I /C:"successfully installed" /C:"already installed" /C:"is already installed" /C:"installed" !WINGET_GIT_TEMP! >nul
    set OUTPUT_CHECK=!ERRORLEVEL!
    if !OUTPUT_CHECK! equ 0 (
        echo Git installed successfully!
    ) else (
        if !WINGET_EXIT! equ 0 (
            REM Exit code was 0, assume success
            echo Git installed successfully!
        ) else (
            echo WARNING: Failed to install Git automatically
            type !WINGET_GIT_TEMP!
        )
    )
    del !WINGET_GIT_TEMP! >nul 2>&1
    echo.
)

REM Install Docker Desktop
where docker >nul 2>nul
if !ERRORLEVEL! neq 0 (
    echo Installing Docker Desktop...
    echo This is a large download and may take several minutes...
    set WINGET_DOCKER_TEMP=temp_winget_docker_%RANDOM%.txt
    winget install Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements >!WINGET_DOCKER_TEMP! 2>&1
    set WINGET_EXIT=!ERRORLEVEL!
    REM Check output for success messages (winget may return non-zero even on success in some cases)
    findstr /I /C:"successfully installed" /C:"already installed" /C:"is already installed" /C:"installed" !WINGET_DOCKER_TEMP! >nul
    set OUTPUT_CHECK=!ERRORLEVEL!
    if !OUTPUT_CHECK! equ 0 (
        echo Docker Desktop installed successfully!
        echo.
        echo IMPORTANT: Docker Desktop needs to be started manually the first time.
        echo Please start Docker Desktop from the Start menu, then run this script again.
    ) else (
        if !WINGET_EXIT! equ 0 (
            REM Exit code was 0, assume success
            echo Docker Desktop installed successfully!
            echo.
            echo IMPORTANT: Docker Desktop needs to be started manually the first time.
            echo Please start Docker Desktop from the Start menu, then run this script again.
        ) else (
            echo WARNING: Failed to install Docker Desktop automatically
            type !WINGET_DOCKER_TEMP!
            echo Please install manually from: https://www.docker.com/products/docker-desktop
        )
    )
    del !WINGET_DOCKER_TEMP! >nul 2>&1
    echo.
)

REM Check and optionally install WSL2 if Docker was just installed
where docker >nul 2>nul
if !ERRORLEVEL! equ 0 (
    REM Only prompt if WSL2 isn't already configured
    where wsl >nul 2>nul
    if !ERRORLEVEL! neq 0 (
        echo.
        echo WSL2 is required for Docker Desktop on Windows.
        echo Would you like to install WSL2 now?
        echo.
        choice /C YN /M "Install WSL2"
        if errorlevel 2 goto :skip_wsl
        if errorlevel 1 (
            call :install_wsl2_now
        )
    ) else (
        REM Check if Virtual Machine Platform is enabled (fast check)
        set WSL_VMP_CHECK=temp_wsl_vmp_%RANDOM%.txt
        dism /online /get-featureinfo /featurename:VirtualMachinePlatform >!WSL_VMP_CHECK! 2>&1
        findstr /I "Enabled" !WSL_VMP_CHECK! >nul
        if !ERRORLEVEL! neq 0 (
            echo.
            echo WSL2 needs Virtual Machine Platform enabled.
            call :install_wsl2_now
        )
        del !WSL_VMP_CHECK! >nul 2>&1
    )
)

:skip_wsl
echo.
echo ========================================
echo   Installation Complete
echo ========================================
echo.

REM Verify installations
set VERIFY_FAILED=0
echo Verifying installations...
echo.

REM Verify Python
python -c "import sys; print('PYTHON_VERSION:', sys.version_info.major, sys.version_info.minor)" >temp_verify_python.txt 2>&1
timeout /t 2 /nobreak >nul
findstr /R "PYTHON_VERSION: 3 11" temp_verify_python.txt >nul
if !ERRORLEVEL! neq 0 (
    echo [ ] Python 3.11 verification failed
    set VERIFY_FAILED=1
) else (
    echo [X] Python 3.11 verified
)
del temp_verify_python.txt >nul 2>&1

REM Verify Git
where git >nul 2>nul
if !ERRORLEVEL! neq 0 (
    echo [ ] Git verification failed
    set VERIFY_FAILED=1
) else (
    echo [X] Git verified
)

REM Verify Docker
where docker >nul 2>nul
if !ERRORLEVEL! neq 0 (
    echo [ ] Docker verification failed
    set VERIFY_FAILED=1
) else (
    echo [X] Docker verified
)

echo.
if !VERIFY_FAILED! equ 1 (
    echo WARNING: Some installations could not be verified.
    echo.
    echo IMPORTANT: If Python or Git were just installed, please:
    echo   1. Close this window
    echo   2. Open a new Command Prompt or PowerShell window
    echo   3. Run %~nx0 again to verify installation
    echo.
    echo This is required for the new PATH to take effect.
) else (
    echo All dependencies verified successfully!
    echo.
    echo Setup complete! You can now start the game.
    echo.
    echo Next steps:
    echo   1. Start servers: cd scripts ^&^& start-servers.bat
    echo   2. Start game client: cd scripts ^&^& start-game.bat
)
echo.
pause
exit /b 0

:manual_install
echo.
echo ========================================
echo   Manual Installation Instructions
echo ========================================
echo.
echo Please install the following manually:
echo.

set MANUAL_PYTHON_CHECK=temp_python_check_%RANDOM%.txt
python -c "import sys; print('PYTHON_VERSION:', sys.version_info.major, sys.version_info.minor)" >!MANUAL_PYTHON_CHECK! 2>&1
timeout /t 2 /nobreak >nul
findstr /R "PYTHON_VERSION: 3 11" !MANUAL_PYTHON_CHECK! >nul
if !ERRORLEVEL! neq 0 (
    echo Python 3.11:
    echo   - Download: https://www.python.org/downloads/
    echo   - IMPORTANT: Check "Add Python to PATH" during installation
    echo   - Or use: winget install Python.Python.3.11
    echo.
)
del !MANUAL_PYTHON_CHECK! >nul 2>&1

where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Git:
    echo   - Download: https://git-scm.com/download/win
    echo   - Or use: winget install Git.Git
    echo.
)

where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Docker Desktop:
    echo   - Download: https://www.docker.com/products/docker-desktop
    echo   - Or use: winget install Docker.DockerDesktop
    echo   - After installation, start Docker Desktop from the Start menu
    echo.
)

echo After installing, close and reopen this window, then run %~nx0 again.
echo.
pause
exit /b 1

:install_wsl2_now
echo.
echo Installing/Configuring WSL2...
echo This may require a system restart.
echo.
REM Enable WSL feature
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [X] WSL feature enabled
) else (
    echo [!] WSL feature may already be enabled
)
REM Enable Virtual Machine Platform (required for WSL2)
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [X] Virtual Machine Platform enabled
) else (
    echo [!] Virtual Machine Platform may already be enabled
)
echo.
echo WSL features enabled. A system restart may be required.
echo.

REM Update WSL to latest version (required for WSL2)
echo [*] Updating WSL to latest version...
wsl --update >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo [X] WSL updated successfully
    REM Now try to set WSL2 as default
    echo [*] Setting WSL2 as default version...
    wsl --set-default-version 2 >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [X] WSL2 set as default version
    ) else (
        echo [!] WSL2 will be set as default after installing a Linux distribution
        echo     Or run manually: wsl --set-default-version 2
    )
) else (
    echo [!] WSL update may need a restart to complete
    echo     After restart, run: wsl --update
    echo     Then: wsl --set-default-version 2
    echo     Or Docker Desktop will configure it automatically
)

echo.
echo IMPORTANT: If prompted, please restart your computer.
echo After restart, WSL2 will be ready for Docker Desktop.
echo.
exit /b

:check_hardware_virtualization
REM Check if hardware virtualization is enabled using PowerShell
REM Sets HARDWARE_VIRT_OK=1 if enabled, 0 otherwise
set VIRT_ENABLED=0
set VIRT_TEMP_CHECK=temp_virt_%RANDOM%.txt

REM Use PowerShell to check for Hyper-V (indicates virtualization is working)
powershell -NoProfile -NonInteractive -Command "(Get-WmiObject -Class Win32_ComputerSystem).HypervisorPresent" >!VIRT_TEMP_CHECK! 2>&1
findstr /I "True" !VIRT_TEMP_CHECK! >nul 2>&1
if !ERRORLEVEL! equ 0 (
    set VIRT_ENABLED=1
)
del !VIRT_TEMP_CHECK! >nul 2>&1

REM If not detected, check Device Guard Virtualization Based Security
if !VIRT_ENABLED! equ 0 (
    powershell -NoProfile -NonInteractive -Command "try { $dg = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction SilentlyContinue; if ($dg.VirtualizationBasedSecurityStatus -ge 1) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set VIRT_ENABLED=1
    )
)

REM Report result and set global variable
if !VIRT_ENABLED! equ 1 (
    echo [X] Hardware Virtualization - ENABLED
    set HARDWARE_VIRT_OK=1
) else (
    echo [!] Hardware Virtualization - STATUS UNKNOWN or DISABLED
    echo     Cannot verify virtualization - assuming disabled
    set HARDWARE_VIRT_OK=0
)
exit /b

:end
pause
