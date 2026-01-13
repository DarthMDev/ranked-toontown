# Toontown Ranked - Python Installation Check
# This script checks if Python is installed and offers to install it if not found
# It installs the latest Python version, not hardcoded to a specific version

param(
    [switch]$Silent = $false
)

# Minimum Python version required
$RequiredMajor = 3
$RequiredMinor = 12

# Function to check if Python command is available and meets version requirements
function Test-PythonCommand {
    param([string]$Command)
    
    try {
        $output = & $Command --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            # Parse version string (e.g., "Python 3.12.0")
            if ($output -match 'Python (\d+)\.(\d+)') {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]
                
                if ($major -gt $RequiredMajor -or ($major -eq $RequiredMajor -and $minor -ge $RequiredMinor)) {
                    return @{
                        Found = $true
                        Command = $Command
                        Version = "$major.$minor"
                    }
                }
                else {
                    return @{
                        Found = $false
                        Reason = "Version $major.$minor is too old (need $RequiredMajor.$RequiredMinor+)"
                    }
                }
            }
        }
    }
    catch {
        # Command not found or failed
    }
    
    return @{ Found = $false; Reason = "Command not found" }
}

# Function to check if Python is installed
function Test-PythonInstalled {
    # Try different Python commands
    $pythonCommands = @('python', 'python3', 'py')
    
    foreach ($cmd in $pythonCommands) {
        $result = Test-PythonCommand -Command $cmd
        if ($result.Found) {
            return $result
        }
    }
    
    return @{ Found = $false; Reason = "No suitable Python installation found" }
}

# Function to install Python using winget
function Install-PythonWithWinget {
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "Python Installation Required" -ForegroundColor Yellow
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Python $RequiredMajor.$RequiredMinor+ is required to run Toontown Ranked." -ForegroundColor White
    Write-Host ""
    
    # Check if winget is available
    try {
        $wingetVersion = winget --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "winget not available"
        }
    }
    catch {
        Write-Host "Error: Windows Package Manager (winget) is not available." -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install Python manually:" -ForegroundColor Yellow
        Write-Host "  1. Visit: https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "  2. Download the latest Python 3.x installer" -ForegroundColor White
        Write-Host "  3. Run the installer and CHECK 'Add Python to PATH'" -ForegroundColor White
        Write-Host "  4. Restart this launcher after installation" -ForegroundColor White
        Write-Host ""
        return $false
    }
    
    # Prompt user for installation
    Write-Host "Would you like to automatically install the latest Python version? (Y/N)" -ForegroundColor Green
    $response = Read-Host
    
    if ($response -notmatch '^[Yy]') {
        Write-Host ""
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "Make sure to check 'Add Python to PATH' during installation!" -ForegroundColor Yellow
        Write-Host ""
        return $false
    }
    
    Write-Host ""
    Write-Host "Installing Python using Windows Package Manager..." -ForegroundColor Cyan
    Write-Host "This may take a few minutes..." -ForegroundColor Gray
    Write-Host ""
    
    # Search for the latest Python.Python package
    try {
        # Install Python using winget (it will get the latest stable version)
        # We use Python.Python.3.13 (or latest available) instead of hardcoding 3.12
        Write-Host "Searching for latest Python version..." -ForegroundColor Gray
        
        # Try to install the latest Python 3.x
        $installArgs = @(
            'install',
            'Python.Python.3.13',  # Try 3.13 first
            '--silent',
            '--accept-package-agreements',
            '--accept-source-agreements',
            '--scope', 'machine'  # Install for all users
        )
        
        $process = Start-Process -FilePath "winget" -ArgumentList $installArgs -NoNewWindow -Wait -PassThru
        
        if ($process.ExitCode -ne 0) {
            # If 3.13 fails, try 3.12
            Write-Host "Python 3.13 not available, trying 3.12..." -ForegroundColor Gray
            $installArgs[1] = 'Python.Python.3.12'
            $process = Start-Process -FilePath "winget" -ArgumentList $installArgs -NoNewWindow -Wait -PassThru
        }
        
        if ($process.ExitCode -eq 0) {
            Write-Host ""
            Write-Host "=" * 70 -ForegroundColor Green
            Write-Host "Python installation completed successfully!" -ForegroundColor Green
            Write-Host "=" * 70 -ForegroundColor Green
            Write-Host ""
            Write-Host "IMPORTANT: Please restart this launcher for changes to take effect." -ForegroundColor Yellow
            Write-Host "Your PATH environment variable has been updated with Python." -ForegroundColor Gray
            Write-Host ""
            return $true
        }
        else {
            Write-Host ""
            Write-Host "Error: Python installation failed (exit code: $($process.ExitCode))" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please install Python manually:" -ForegroundColor Yellow
            Write-Host "  1. Visit: https://www.python.org/downloads/" -ForegroundColor White
            Write-Host "  2. Download and run the installer" -ForegroundColor White
            Write-Host "  3. Check 'Add Python to PATH' during installation" -ForegroundColor White
            Write-Host ""
            return $false
        }
    }
    catch {
        Write-Host ""
        Write-Host "Error during installation: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install Python manually from: https://www.python.org/downloads/" -ForegroundColor White
        Write-Host ""
        return $false
    }
}

# Main script logic
if (-not $Silent) {
    Write-Host "Checking for Python installation..." -ForegroundColor Cyan
}

$pythonCheck = Test-PythonInstalled

if ($pythonCheck.Found) {
    if (-not $Silent) {
        Write-Host "Found Python $($pythonCheck.Version) using command: $($pythonCheck.Command)" -ForegroundColor Green
    }
    
    # Write the Python command to PPYTHON_PATH file for the batch script
    $ppythonPath = Join-Path $PSScriptRoot "PPYTHON_PATH"
    $pythonCheck.Command | Out-File -FilePath $ppythonPath -Encoding ASCII -NoNewline
    
    exit 0  # Success
}
else {
    if (-not $Silent) {
        Write-Host "Python check failed: $($pythonCheck.Reason)" -ForegroundColor Red
        Write-Host ""
    }
    
    # Offer to install Python
    $installed = Install-PythonWithWinget
    
    if ($installed) {
        Write-Host "Please close this window and restart the launcher." -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 2  # Python was installed, needs restart
    }
    else {
        Write-Host "Cannot continue without Python." -ForegroundColor Red
        Write-Host ""
        if (-not $Silent) {
            Read-Host "Press Enter to exit"
        }
        exit 1  # Failure
    }
}
