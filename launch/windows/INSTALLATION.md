# Windows Installation Guide

## Automatic Dependency Management

As of this update, the Toontown Ranked launcher includes automatic Python and MongoDB detection and installation!

### How It Works (Hybrid Approach)

The launcher uses a **two-path dependency checking system**:

#### Path 1: Batch File Users (End Users)
1. **Pre-Flight Check**: Before running any Python code, the launcher runs `check_dependencies.ps1` (PowerShell)
2. **Python Detection**: Checks for Python 3.12+ using common commands (`python`, `python3`, `py`)
3. **MongoDB Detection**: Checks for MongoDB in PATH and common installation locations
4. **Automatic Installation**: Offers to install missing dependencies using Windows Package Manager (winget)
5. **Version Selection**: Installer tries to get the latest versions (Python 3.13 → 3.12, MongoDB latest)
6. **No Python Code**: This all happens BEFORE any Python code runs, solving the "no Python" problem

#### Path 2: PyCharm/Direct Python Users (Developers)
1. **Python Already Available**: PyCharm runs Python directly, so Python is guaranteed to be available
2. **Python-Based Check**: `dependency_checker.py` runs to verify MongoDB and other dependencies
3. **Less Intrusive**: Respects `DEVELOPER_MODE` and `SKIP_DEPENDENCY_CHECK` environment variables
4. **Cross-Platform**: Works on Windows, Linux, and macOS

### What This Solves

**Before**: Users without Python would see this confusing message:
```
Checking dependencies...
Python was not found; run without arguments to install from the Microsoft Store, or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
```

**Now**: Users get a clear, helpful prompt for both Python and MongoDB:
```
Verifying Python installation...

======================================================================
Python Installation Required
======================================================================

Python 3.12+ is required to run Toontown Ranked.

Would you like to automatically install the latest Python version? (Y/N)
```

And for MongoDB:
```
Checking MongoDB installation...
✗ MongoDB not found: MongoDB not found in PATH or common installation locations
MongoDB is REQUIRED to run Toontown Ranked.

Would you like to install MongoDB automatically? (y/n):
```

**Important**: MongoDB is now **required** to run Toontown Ranked. Users cannot proceed without it

### Files Modified

- **`check_dependencies.ps1`** (NEW): PowerShell script that handles Python AND MongoDB detection/installation
- **`dependency_checker.py`** (UPDATED): Python-based checker for direct Python launches (PyCharm, etc.)
- **`start-game.bat`**: Updated to use the new comprehensive dependency checker
- **`start-server-astron.bat`**: Updated to use the new comprehensive dependency checker
- **`start-server-ai.bat`**: Updated to use the new comprehensive dependency checker
- **`start-server-uberdog.bat`**: Updated to use the new comprehensive dependency checker
- **`PPYTHON_PATH`**: Generated automatically by the PowerShell checker (stores the Python command to use)

### Technical Details

#### Exit Codes
The `check_dependencies.ps1` script returns:
- `0`: All dependencies found and meet requirements
- `1`: Dependencies missing and installation failed/declined
- `2`: Dependencies were just installed, launcher needs restart

#### Version Strategy
Instead of hardcoding versions, the script installs the **latest available** versions:
- **Python**: Tries `Python.Python.3.13` → `Python.Python.3.12`
- **MongoDB**: Installs latest `MongoDB.Server`

#### PPYTHON_PATH File
The PowerShell checker creates a `PPYTHON_PATH` file containing the Python command that works on the user's system (e.g., `python`, `py`, etc.). This file is used by subsequent scripts and is automatically ignored by git.

#### Why Two Checkers?
- **PowerShell (`check_dependencies.ps1`)**: For end users launching via batch files. Runs BEFORE Python is available.
- **Python (`dependency_checker.py`)**: For developers launching directly from PyCharm/IDE. Python is already running.

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
