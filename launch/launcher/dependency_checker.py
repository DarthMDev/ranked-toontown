"""
Dependency checker for Toontown Ranked.
Checks for Python 3.12+ and MongoDB installation, and offers to install them if missing.
"""
import sys
import subprocess
import platform
import os
import urllib.request
import tempfile
import shutil
import glob
from typing import Tuple, Optional

# Required Python version (minimum)
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 12

# MongoDB version check (optional, but recommended)
MONGODB_MIN_VERSION = (4, 0)  # Minimum MongoDB version


def check_python_version() -> Tuple[bool, Optional[str], Optional[Tuple[int, int]]]:
    """
    Check if Python 3.12+ is installed.
    Returns: (is_installed, error_message, version_tuple)
    """
    try:
        version = sys.version_info
        version_tuple = (version.major, version.minor)
        
        if version.major < REQUIRED_PYTHON_MAJOR or \
           (version.major == REQUIRED_PYTHON_MAJOR and version.minor < REQUIRED_PYTHON_MINOR):
            return False, f"Python {REQUIRED_PYTHON_MAJOR}.{REQUIRED_PYTHON_MINOR}+ is required, but found {version.major}.{version.minor}", version_tuple
        
        return True, None, version_tuple
    except Exception as e:
        return False, f"Error checking Python version: {str(e)}", None


def check_python_in_path() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if Python is available in PATH.
    Returns: (is_available, python_path, error_message)
    """
    python_commands = ['python', 'python3', 'py']
    
    for cmd in python_commands:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check version
                version_output = result.stdout.strip() or result.stderr.strip()
                # Extract version numbers
                try:
                    version_str = version_output.split()[1]
                    major, minor = map(int, version_str.split('.')[:2])
                    if major >= REQUIRED_PYTHON_MAJOR and \
                       (major > REQUIRED_PYTHON_MAJOR or minor >= REQUIRED_PYTHON_MINOR):
                        return True, cmd, None
                except (ValueError, IndexError):
                    continue
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        except Exception:
            continue
    
    return False, None, "Python not found in PATH"


def check_mongodb() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if MongoDB is installed and accessible.
    Returns: (is_installed, version_string, error_message)
    """
    # First try PATH
    try:
        result = subprocess.run(
            ['mongod', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_output = result.stdout.strip() or result.stderr.strip()
            # Extract version from output like "db version v7.0.0"
            for line in version_output.split('\n'):
                if 'version' in line.lower():
                    return True, line.strip(), None
            return True, version_output.split('\n')[0] if version_output else "MongoDB installed", None
    except FileNotFoundError:
        pass  # Continue to check common paths
    except subprocess.TimeoutExpired:
        return False, None, "MongoDB check timed out"
    except Exception:
        pass  # Continue to check common paths
    
    # On Windows, check common installation paths
    if platform.system() == 'Windows':
        common_paths = [
            r'C:\Program Files\MongoDB\Server\*\bin\mongod.exe',
            r'C:\Program Files (x86)\MongoDB\Server\*\bin\mongod.exe',
            os.path.expanduser(r'~\AppData\Local\Programs\MongoDB\Server\*\bin\mongod.exe'),
        ]
        
        for path_pattern in common_paths:
            matches = glob.glob(path_pattern)
            if matches:
                # Found MongoDB, try to get version
                mongod_path = matches[0]
                try:
                    result = subprocess.run(
                        [mongod_path, '--version'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        version_output = result.stdout.strip() or result.stderr.strip()
                        for line in version_output.split('\n'):
                            if 'version' in line.lower():
                                return True, f"{line.strip()} (found at {mongod_path})", None
                        return True, f"MongoDB installed (found at {mongod_path})", None
                except Exception:
                    continue
        
        # Check if MongoDB service is installed (even if not in PATH)
        try:
            result = subprocess.run(
                ['sc', 'query', 'MongoDB'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and 'MongoDB' in result.stdout:
                return False, None, "MongoDB is installed but not in PATH. Please add MongoDB bin directory to your PATH or restart your terminal."
        except Exception:
            pass
    
    return False, None, "MongoDB not found in PATH or common installation locations"


def install_python_windows() -> bool:
    """
    Attempt to install Python on Windows.
    Returns True if installation was successful or initiated.
    """
    system = platform.system()
    if system != 'Windows':
        print("Automatic Python installation is only supported on Windows.")
        print(f"Please install Python {REQUIRED_PYTHON_MAJOR}.{REQUIRED_PYTHON_MINOR}+ manually from https://www.python.org/downloads/")
        return False
    
    # Try using winget first (Windows Package Manager)
    try:
        result = subprocess.run(
            ['winget', '--version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("Installing Python using winget...")
            result = subprocess.run(
                ['winget', 'install', 'Python.Python.3.12', '--silent', '--accept-package-agreements', '--accept-source-agreements'],
                timeout=300
            )
            if result.returncode == 0:
                print("Python installation completed. Please restart your terminal and try again.")
                return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        print(f"winget installation failed: {e}")
    
    # Fallback: Download installer
    print("winget not available. Downloading Python installer...")
    try:
        python_url = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
        installer_path = os.path.join(tempfile.gettempdir(), "python-installer.exe")
        
        print(f"Downloading Python installer to {installer_path}...")
        urllib.request.urlretrieve(python_url, installer_path)
        
        print("Launching Python installer...")
        print("IMPORTANT: Please check 'Add Python to PATH' during installation!")
        # Use /passive to show installer UI so user can check "Add Python to PATH"
        # PrependPath=1 should add to PATH automatically, but user should verify
        subprocess.Popen([installer_path, '/passive', 'InstallAllUsers=1', 'PrependPath=1'])
        
        print("Python installer launched. Please complete the installation and restart your terminal.")
        return True
    except Exception as e:
        print(f"Failed to download/install Python: {e}")
        print(f"Please install Python {REQUIRED_PYTHON_MAJOR}.{REQUIRED_PYTHON_MINOR}+ manually from https://www.python.org/downloads/")
        return False


def install_mongodb_windows() -> bool:
    """
    Attempt to install MongoDB on Windows.
    Returns True if installation was successful or initiated.
    """
    system = platform.system()
    if system != 'Windows':
        print("Automatic MongoDB installation is only supported on Windows.")
        print("Please install MongoDB manually from https://www.mongodb.com/try/download/community")
        return False
    
    # Try using winget first
    try:
        result = subprocess.run(
            ['winget', '--version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("Installing MongoDB using winget...")
            result = subprocess.run(
                ['winget', 'install', 'MongoDB.Server', '--silent', '--accept-package-agreements', '--accept-source-agreements'],
                timeout=600
            )
            if result.returncode == 0:
                print("\n" + "=" * 60)
                print("MongoDB installation completed!")
                print("=" * 60)
                print("\nIMPORTANT: MongoDB may not be immediately available in your PATH.")
                print("Please do ONE of the following:")
                print("  1. Restart your terminal/command prompt and try again")
                print("  2. Or manually add MongoDB to your PATH:")
                print("     - Find MongoDB installation (usually in Program Files\\MongoDB\\Server\\<version>\\bin)")
                print("     - Add that path to your system PATH environment variable")
                print("\nAfter restarting or updating PATH, the dependency checker will detect MongoDB.")
                print("=" * 60 + "\n")
                return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        print(f"winget installation failed: {e}")
    
    # Fallback: Provide download link
    print("winget not available. Please install MongoDB manually.")
    print("Download MongoDB from: https://www.mongodb.com/try/download/community")
    print("After installation, make sure to add MongoDB to your PATH.")
    return False


def install_python_linux() -> bool:
    """
    Attempt to install Python on Linux.
    """
    print("Attempting to install Python using package manager...")
    
    # Detect package manager
    package_managers = [
        ('apt-get', ['sudo', 'apt-get', 'update', '&&', 'sudo', 'apt-get', 'install', '-y', 'python3.12']),
        ('yum', ['sudo', 'yum', 'install', '-y', 'python3.12']),
        ('dnf', ['sudo', 'dnf', 'install', '-y', 'python3.12']),
        ('pacman', ['sudo', 'pacman', '-S', '--noconfirm', 'python']),
    ]
    
    for pm_name, cmd in package_managers:
        try:
            result = subprocess.run(['which', pm_name], capture_output=True, timeout=5)
            if result.returncode == 0:
                print(f"Using {pm_name} to install Python...")
                # Note: This would require user to run with sudo
                print(f"Please run: {' '.join(cmd)}")
                return False
        except Exception:
            continue
    
    print("Please install Python 3.12+ manually using your system's package manager.")
    return False


def install_mongodb_linux() -> bool:
    """
    Attempt to install MongoDB on Linux.
    """
    print("Please install MongoDB manually using your system's package manager.")
    print("See: https://www.mongodb.com/docs/manual/installation/")
    return False


def install_python_macos() -> bool:
    """
    Attempt to install Python on macOS.
    """
    # Check for Homebrew
    try:
        result = subprocess.run(['which', 'brew'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print("Installing Python using Homebrew...")
            print("Please run: brew install python@3.12")
            return False
    except Exception:
        pass
    
    print("Please install Python 3.12+ manually.")
    print("You can use Homebrew: brew install python@3.12")
    print("Or download from: https://www.python.org/downloads/")
    return False


def install_mongodb_macos() -> bool:
    """
    Attempt to install MongoDB on macOS.
    """
    # Check for Homebrew
    try:
        result = subprocess.run(['which', 'brew'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print("Installing MongoDB using Homebrew...")
            print("Please run: brew tap mongodb/brew && brew install mongodb-community")
            return False
    except Exception:
        pass
    
    print("Please install MongoDB manually.")
    print("You can use Homebrew: brew tap mongodb/brew && brew install mongodb-community")
    print("Or download from: https://www.mongodb.com/try/download/community")
    return False


def check_dependencies(require_mongodb: bool = False, quiet: bool = False) -> bool:
    """
    Check all dependencies and prompt for installation if missing.
    Returns True if all required dependencies are met.
    
    Args:
        require_mongodb: If True, MongoDB is required. If False, it's optional but recommended.
        quiet: If True, don't print headers and be less verbose (for developer mode).
    """
    if not quiet:
        print("=" * 60)
        print("Toontown Ranked - Dependency Checker")
        print("=" * 60)
        print()
    
    all_ok = True
    
    # Check Python version (required)
    if not quiet:
        print("Checking Python installation...")
    python_ok, error_msg, version = check_python_version()
    
    if python_ok:
        if not quiet:
            print(f"✓ Python {version[0]}.{version[1]} is installed and compatible.")
    else:
        if not quiet:
            print(f"✗ Python check failed: {error_msg}")
        all_ok = False
        
        # Also check if Python is in PATH
        path_ok, python_path, path_error = check_python_in_path()
        if not path_ok and not quiet:
            print(f"  Note: {path_error}")
        
        if not quiet:
            print()
            response = input(f"Would you like to install Python {REQUIRED_PYTHON_MAJOR}.{REQUIRED_PYTHON_MINOR}+? (y/n): ").strip().lower()
        else:
            response = 'n'  # In quiet mode, don't prompt, just report
        
        if response == 'y':
            system = platform.system()
            if system == 'Windows':
                install_python_windows()
            elif system == 'Linux':
                install_python_linux()
            elif system == 'Darwin':
                install_python_macos()
            else:
                print(f"Automatic installation not supported on {system}. Please install manually.")
            return False  # Need to restart after installation
        else:
            if not quiet:
                print("Python installation is required to continue.")
            return False
    
    if not quiet:
        print()
    
    # Check MongoDB (optional but recommended)
    if not quiet:
        print("Checking MongoDB installation...")
    mongodb_ok, mongodb_version, mongodb_error = check_mongodb()
    
    if mongodb_ok:
        if not quiet:
            print(f"✓ MongoDB is installed: {mongodb_version}")
    else:
        if not quiet:
            print(f"⚠ MongoDB not found: {mongodb_error}")
        if require_mongodb:
            all_ok = False
            if not quiet:
                print("MongoDB is required for this configuration.")
                print()
                response = input("Would you like to install MongoDB? (y/n): ").strip().lower()
            else:
                response = 'n'  # In quiet mode, don't prompt, just report
            
            if response == 'y':
                system = platform.system()
                if system == 'Windows':
                    install_mongodb_windows()
                elif system == 'Linux':
                    install_mongodb_linux()
                elif system == 'Darwin':
                    install_mongodb_macos()
                else:
                    print(f"Automatic installation not supported on {system}. Please install manually.")
                return False  # Need to restart after installation
            else:
                if not quiet:
                    print("MongoDB installation is required to continue.")
                return False
        else:
            if not quiet:
                print("MongoDB is optional. The game will use YAML backend for data storage.")
                print("MongoDB is recommended for better performance and features.")
                print()
                response = input("Would you like to install MongoDB? (y/n): ").strip().lower()
            else:
                response = 'n'  # In quiet mode, don't prompt, just report
            
            if response == 'y':
                system = platform.system()
                if system == 'Windows':
                    install_mongodb_windows()
                elif system == 'Linux':
                    install_mongodb_linux()
                elif system == 'Darwin':
                    install_mongodb_macos()
                else:
                    print(f"Automatic installation not supported on {system}. Please install manually.")
                # MongoDB installation doesn't require immediate restart, but it's recommended
            else:
                if not quiet:
                    print()
                    print("⚠ WARNING: Proceeding without MongoDB.")
                    print("The game will use YAML backend for data storage, which may have limitations.")
                    response = input("Continue anyway? (y/n): ").strip().lower()
                else:
                    response = 'y'  # In quiet mode, allow proceeding
                
                if response != 'y':
                    if not quiet:
                        print("Launch cancelled. Please install MongoDB and try again.")
                    return False
    
    if not quiet:
        print()
        print("=" * 60)
        
        if all_ok:
            print("All dependencies are satisfied!")
        else:
            print("Some dependencies are missing. Please install them and try again.")
        
        print("=" * 60)
        print()
    
    return all_ok


if __name__ == '__main__':
    # Allow command-line argument to require MongoDB
    require_mongo = '--require-mongodb' in sys.argv
    success = check_dependencies(require_mongodb=require_mongo)
    sys.exit(0 if success else 1)
