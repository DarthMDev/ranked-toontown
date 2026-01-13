# Windows Installation Guide

## Automatic Python Installation

As of this update, the Toontown Ranked launcher includes automatic Python detection and installation!

### How It Works

1. **Pre-Flight Check**: Before running any Python code, the launcher runs `check_python.ps1` to verify Python is installed
2. **Smart Detection**: The script checks for Python 3.12+ using common commands (`python`, `python3`, `py`)
3. **Automatic Installation**: If Python is not found, the script offers to automatically install the **latest** Python version using Windows Package Manager (winget)
4. **Version Selection**: The installer tries to get the most recent Python version available (3.13, then 3.12 if 3.13 isn't available)
5. **Graceful Fallback**: If automatic installation fails, the script provides clear instructions for manual installation

### What This Solves

**Before**: Users without Python would see this confusing message:
```
Checking dependencies...
Python was not found; run without arguments to install from the Microsoft Store, or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
```

**Now**: Users get a clear, helpful prompt:
```
Verifying Python installation...

======================================================================
Python Installation Required
======================================================================

Python 3.12+ is required to run Toontown Ranked.

Would you like to automatically install the latest Python version? (Y/N)
```

### Files Modified

- **`check_python.ps1`** (NEW): PowerShell script that handles Python detection and installation
- **`start-game.bat`**: Updated to use the new Python checker
- **`start-server-astron.bat`**: Updated to use the new Python checker  
- **`start-server-ai.bat`**: Updated to use the new Python checker
- **`start-server-uberdog.bat`**: Updated to use the new Python checker
- **`PPYTHON_PATH`**: Generated automatically by the checker (stores the Python command to use)

### Technical Details

#### Exit Codes
The `check_python.ps1` script returns:
- `0`: Python found and meets requirements
- `1`: Python not found and installation failed/declined
- `2`: Python was just installed, launcher needs restart

#### Python Version Strategy
Instead of hardcoding Python 3.12, the script installs the **latest available** Python 3.x version:
1. First tries: `Python.Python.3.13`
2. Falls back to: `Python.Python.3.12`
3. Manual instructions provided if both fail

#### PPYTHON_PATH File
The checker creates a `PPYTHON_PATH` file containing the Python command that works on the user's system (e.g., `python`, `py`, etc.). This file is used by subsequent scripts and is automatically ignored by git.

### Manual Installation

If you prefer to install Python manually or the automatic installer doesn't work:

1. Download Python 3.12+ from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Restart your computer
5. Run the launcher again

### Troubleshooting

**Q: The automatic installer says winget is not available**
A: Windows Package Manager (winget) requires Windows 10 version 1809+ or Windows 11. If you have an older version, please install Python manually.

**Q: The installer completed but the launcher still can't find Python**
A: Try restarting your command prompt or computer. Windows needs to refresh environment variables.

**Q: I want to use a specific Python installation**
A: Manually edit the `PPYTHON_PATH` file and enter the full path to your Python executable (e.g., `C:\Python312\python.exe`).

### For Developers

If you're developing and want to skip the dependency check entirely:
```batch
set SKIP_DEPENDENCY_CHECK=1
```

Or for a non-blocking check:
```batch
set DEVELOPER_MODE=1
```
