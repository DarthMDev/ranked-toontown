# Toontown Ranked - Dependency Checker (PowerShell)
# This script checks if Python and MongoDB are installed and offers to install them if not found
# This runs BEFORE any Python code, solving the "no Python installed" problem

param(
    [switch]$Silent = $false
)

# Minimum Python version required
$RequiredPythonMajor = 3
$RequiredPythonMinor = 12

# Exit codes
$EXIT_SUCCESS = 0
$EXIT_FAILURE = 1
$EXIT_RESTART_NEEDED = 2

#region Python Functions

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
                
                if ($major -gt $RequiredPythonMajor -or ($major -eq $RequiredPythonMajor -and $minor -ge $RequiredPythonMinor)) {
                    return @{
                        Found = $true
                        Command = $Command
                        Version = "$major.$minor"
                    }
                }
                else {
                    return @{
                        Found = $false
                        Reason = "Version $major.$minor is too old (need $RequiredPythonMajor.$RequiredPythonMinor+)"
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
    Write-Host "Python $RequiredPythonMajor.$RequiredPythonMinor+ is required to run Toontown Ranked." -ForegroundColor White
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
            Write-Host "Refreshing environment to detect Python..." -ForegroundColor Gray
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

#endregion

#region MongoDB Functions

# Function to check if MongoDB is installed
function Test-MongoDBInstalled {
    # Try mongod command in PATH first
    try {
        $output = mongod --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $versionLine = ($output | Select-String -Pattern "version").Line
            if ($versionLine) {
                return @{
                    Found = $true
                    Version = $versionLine.Trim()
                    Path = "mongod (in PATH)"
                }
            }
            return @{
                Found = $true
                Version = "MongoDB installed"
                Path = "mongod (in PATH)"
            }
        }
    }
    catch {
        # Continue to check common paths
    }
    
    # Check common installation paths on Windows
    $commonPaths = @(
        "C:\Program Files\MongoDB\Server\*\bin\mongod.exe",
        "C:\Program Files (x86)\MongoDB\Server\*\bin\mongod.exe",
        "$env:USERPROFILE\AppData\Local\Programs\MongoDB\Server\*\bin\mongod.exe"
    )
    
    foreach ($pathPattern in $commonPaths) {
        $matches = Get-ChildItem -Path $pathPattern -ErrorAction SilentlyContinue
        if ($matches) {
            $mongodPath = $matches[0].FullName
            try {
                $output = & $mongodPath --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $versionLine = ($output | Select-String -Pattern "version").Line
                    if ($versionLine) {
                        return @{
                            Found = $true
                            Version = $versionLine.Trim()
                            Path = $mongodPath
                            NotInPath = $true
                        }
                    }
                }
            }
            catch {
                continue
            }
        }
    }
    
    # Check if MongoDB service is installed
    try {
        $service = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
        if ($service) {
            return @{
                Found = $false
                Reason = "MongoDB is installed but not in PATH. Please add MongoDB bin directory to your PATH or restart your terminal."
                ServiceFound = $true
            }
        }
    }
    catch {
        # Service not found
    }
    
    return @{
        Found = $false
        Reason = "MongoDB not found in PATH or common installation locations"
    }
}

# Function to install MongoDB using winget
function Install-MongoDBWithWinget {
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "MongoDB Installation Required" -ForegroundColor Yellow
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
    Write-Host "MongoDB is REQUIRED to run Toontown Ranked." -ForegroundColor White
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
        Write-Host "Please install MongoDB manually:" -ForegroundColor Yellow
        Write-Host "  • Download from: https://www.mongodb.com/try/download/community" -ForegroundColor White
        Write-Host "  • Or install via Chocolatey: choco install mongodb" -ForegroundColor White
        Write-Host ""
        Write-Host "After installation:" -ForegroundColor Yellow
        Write-Host "  1. Ensure MongoDB is added to your system PATH" -ForegroundColor White
        Write-Host "  2. Restart this launcher" -ForegroundColor White
        Write-Host ""
        return $false
    }
    
    # Prompt user for installation
    Write-Host "Would you like to automatically install MongoDB? (Y/N)" -ForegroundColor Green
    $response = Read-Host
    
    if ($response -notmatch '^[Yy]') {
        Write-Host ""
        Write-Host "=" * 70 -ForegroundColor Yellow
        Write-Host "MongoDB Installation Required" -ForegroundColor Yellow
        Write-Host "=" * 70 -ForegroundColor Yellow
        Write-Host "Toontown Ranked requires MongoDB to run." -ForegroundColor White
        Write-Host ""
        Write-Host "Please install MongoDB manually:" -ForegroundColor Yellow
        Write-Host "  • Windows: https://www.mongodb.com/try/download/community" -ForegroundColor White
        Write-Host "  • Or use winget: winget install MongoDB.Server" -ForegroundColor White
        Write-Host ""
        Write-Host "After installing MongoDB:" -ForegroundColor Yellow
        Write-Host "  1. Ensure MongoDB is added to your system PATH" -ForegroundColor White
        Write-Host "  2. Restart this launcher" -ForegroundColor White
        Write-Host "=" * 70 -ForegroundColor Yellow
        Write-Host ""
        return $false
    }
    
    Write-Host ""
    Write-Host "Installing MongoDB using Windows Package Manager..." -ForegroundColor Cyan
    Write-Host "This may take several minutes..." -ForegroundColor Gray
    Write-Host ""
    
    try {
        $installArgs = @(
            'install',
            'MongoDB.Server',
            '--silent',
            '--accept-package-agreements',
            '--accept-source-agreements',
            '--scope', 'machine'
        )
        
        $process = Start-Process -FilePath "winget" -ArgumentList $installArgs -NoNewWindow -Wait -PassThru
        
        if ($process.ExitCode -eq 0) {
            Write-Host ""
            Write-Host "=" * 70 -ForegroundColor Green
            Write-Host "MongoDB installation completed successfully!" -ForegroundColor Green
            Write-Host "=" * 70 -ForegroundColor Green
            Write-Host ""
            Write-Host "Refreshing environment to detect MongoDB..." -ForegroundColor Gray
            return $true
        }
        else {
            Write-Host ""
            Write-Host "Error: MongoDB installation failed (exit code: $($process.ExitCode))" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please install MongoDB manually:" -ForegroundColor Yellow
            Write-Host "  • Download from: https://www.mongodb.com/try/download/community" -ForegroundColor White
            Write-Host ""
            return $false
        }
    }
    catch {
        Write-Host ""
        Write-Host "Error during installation: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install MongoDB manually from:" -ForegroundColor Yellow
        Write-Host "https://www.mongodb.com/try/download/community" -ForegroundColor White
        Write-Host ""
        return $false
    }
}

#endregion

#region Helper Functions

# Function to refresh environment variables from registry
function Update-EnvironmentVariables {
    Write-Host "Refreshing environment variables..." -ForegroundColor Gray
    
    # Get Machine PATH
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    # Get User PATH
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    # Combine them (User PATH takes precedence)
    $newPath = "$userPath;$machinePath"
    
    # Update current process PATH
    $env:Path = $newPath
    
    Write-Host "Environment variables refreshed." -ForegroundColor Gray
}

#endregion

#region Main Script

if (-not $Silent) {
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "Toontown Ranked - Dependency Checker" -ForegroundColor White
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
}

$allOk = $true
$needsRestart = $false

# Check Python
if (-not $Silent) {
    Write-Host "Checking Python installation..." -ForegroundColor Cyan
}

$pythonCheck = Test-PythonInstalled

if ($pythonCheck.Found) {
    if (-not $Silent) {
        Write-Host "  Found Python $($pythonCheck.Version) using command: $($pythonCheck.Command)" -ForegroundColor Green
    }
    
    # Write the Python command to PPYTHON_PATH file for the batch script
    $ppythonPath = Join-Path $PSScriptRoot "PPYTHON_PATH"
    $pythonCheck.Command | Out-File -FilePath $ppythonPath -Encoding ASCII -NoNewline
}
else {
    if (-not $Silent) {
        Write-Host "  Python check failed: $($pythonCheck.Reason)" -ForegroundColor Red
    }
    
    $allOk = $false
    
    # Offer to install Python
    $installed = Install-PythonWithWinget
    
    if ($installed) {
        # Refresh environment variables to pick up newly installed Python
        Write-Host ""
        Update-EnvironmentVariables
        Write-Host ""
        Write-Host "Re-checking Python installation..." -ForegroundColor Cyan
        
        # Re-check if Python is now available
        $pythonCheck = Test-PythonInstalled
        
        if ($pythonCheck.Found) {
            Write-Host "  Python $($pythonCheck.Version) detected successfully!" -ForegroundColor Green
            $allOk = $true
            
            # Write the Python command to PPYTHON_PATH file
            $ppythonPath = Join-Path $PSScriptRoot "PPYTHON_PATH"
            $pythonCheck.Command | Out-File -FilePath $ppythonPath -Encoding ASCII -NoNewline
        }
        else {
            Write-Host "  Python installed but not yet available in PATH." -ForegroundColor Yellow
            Write-Host "  Please restart this launcher for changes to take effect." -ForegroundColor Yellow
            $needsRestart = $true
        }
    }
    else {
        Write-Host "Cannot continue without Python." -ForegroundColor Red
        Write-Host ""
        if (-not $Silent) {
            Read-Host "Press Enter to exit"
        }
        exit $EXIT_FAILURE
    }
}

# Check MongoDB
if (-not $Silent) {
    Write-Host ""
    Write-Host "Checking MongoDB installation..." -ForegroundColor Cyan
}

$mongoCheck = Test-MongoDBInstalled

if ($mongoCheck.Found) {
    if (-not $Silent) {
        Write-Host "  Found MongoDB: $($mongoCheck.Version)" -ForegroundColor Green
        if ($mongoCheck.NotInPath) {
            Write-Host "  Note: MongoDB found at $($mongoCheck.Path) but not in PATH" -ForegroundColor Yellow
        }
    }
}
else {
    if (-not $Silent) {
        Write-Host "  MongoDB not found: $($mongoCheck.Reason)" -ForegroundColor Red
    }
    
    $allOk = $false
    
    # Offer to install MongoDB
    $installed = Install-MongoDBWithWinget
    
    if ($installed) {
        # Refresh environment variables to pick up newly installed MongoDB
        Write-Host ""
        Update-EnvironmentVariables
        Write-Host ""
        Write-Host "Re-checking MongoDB installation..." -ForegroundColor Cyan
        
        # Re-check if MongoDB is now available
        $mongoCheck = Test-MongoDBInstalled
        
        if ($mongoCheck.Found) {
            Write-Host "  MongoDB detected successfully!" -ForegroundColor Green
            $allOk = $true
        }
        else {
            Write-Host "  MongoDB installed but not yet available in PATH." -ForegroundColor Yellow
            Write-Host "  Please restart this launcher for changes to take effect." -ForegroundColor Yellow
            $needsRestart = $true
        }
    }
    else {
        Write-Host "Cannot continue without MongoDB." -ForegroundColor Red
        Write-Host ""
        if (-not $Silent) {
            Read-Host "Press Enter to exit"
        }
        exit $EXIT_FAILURE
    }
}

# Final status
if (-not $Silent) {
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    
    if ($needsRestart) {
        Write-Host "Dependencies installed but require restart!" -ForegroundColor Yellow
        Write-Host "=" * 70 -ForegroundColor Cyan
        Write-Host ""
        Write-Host "The dependencies were installed successfully, but are not yet" -ForegroundColor White
        Write-Host "available in the current session. Please restart this launcher." -ForegroundColor White
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit $EXIT_RESTART_NEEDED
    }
    elseif ($allOk) {
        Write-Host "All dependencies are satisfied!" -ForegroundColor Green
        Write-Host "=" * 70 -ForegroundColor Cyan
        Write-Host ""
    }
    else {
        Write-Host "Some dependencies are missing. Please install them and try again." -ForegroundColor Red
        Write-Host "=" * 70 -ForegroundColor Cyan
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit $EXIT_FAILURE
    }
}

exit $EXIT_SUCCESS

#endregion
