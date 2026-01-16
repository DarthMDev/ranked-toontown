#!/bin/bash
# Toontown Ranked: Installation Wizard

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    echo "Toontown Ranked - Installation Wizard"
    echo ""
    echo "This script checks and installs required dependencies:"
    echo "  - Python 3.11"
    echo "  - Git"
    echo "  - Docker"
    echo ""
    echo "Usage: $SCRIPT_NAME [--help]"
    echo ""
    exit 0
fi

# Change to script directory
cd "$(dirname "$0")" || exit 1

echo "========================================"
echo "  Toontown Ranked - Installation Wizard"
echo "========================================"
echo ""

MISSING_COUNT=0
INSTALL_LIST=()

# Function to check if sudo is available
check_sudo() {
    if ! command -v sudo &> /dev/null; then
        return 1
    fi
    sudo -n true 2>/dev/null || return 1
    return 0
}

# Check Python 3.11
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "[X] Python 3.11 - INSTALLED"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '3\.11(\.[0-9]+)?' || echo "")
    if [ "$PYTHON_VERSION" == "3.11" ] || [[ "$PYTHON_VERSION" =~ ^3\.11\. ]]; then
        PYTHON_CMD="python3"
        echo "[X] Python 3.11 - INSTALLED"
    else
        MISSING_COUNT=$((MISSING_COUNT + 1))
        INSTALL_LIST+=("Python")
        echo "[ ] Python 3.11 - WRONG VERSION"
        python3 --version || true
    fi
else
    MISSING_COUNT=$((MISSING_COUNT + 1))
    INSTALL_LIST+=("Python")
    echo "[ ] Python 3.11 - NOT INSTALLED"
fi

# Check Git
if command -v git &> /dev/null; then
    echo "[X] Git - INSTALLED"
else
    MISSING_COUNT=$((MISSING_COUNT + 1))
    INSTALL_LIST+=("Git")
    echo "[ ] Git - NOT INSTALLED"
fi

# Check Docker
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo "[X] Docker - INSTALLED AND RUNNING"
    else
        echo "[~] Docker - INSTALLED BUT NOT RUNNING"
        # On Linux, check if Docker service exists and can be started
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if systemctl is-active --quiet docker 2>/dev/null || systemctl is-enabled --quiet docker 2>/dev/null; then
                echo "    Docker service exists. You may need to start it with: sudo systemctl start docker"
            else
                echo "    Docker service will be started automatically when needed"
            fi
        else
            echo "    Docker service will be started automatically when needed"
        fi
    fi
else
    MISSING_COUNT=$((MISSING_COUNT + 1))
    INSTALL_LIST+=("Docker")
    echo "[ ] Docker - NOT INSTALLED"
fi

echo ""

# If all dependencies are installed
if [ $MISSING_COUNT -eq 0 ]; then
    echo "All dependencies are installed!"
    echo ""
    echo "Setup complete! You can now start the game."
    echo ""
    echo "Next steps:"
    echo "  1. Start servers: cd scripts && ./start-servers.sh"
    echo "  2. Start game client: cd scripts && ./start-game.sh"
    echo ""
    exit 0
fi

# Show installation instructions
echo "========================================"
echo "  Missing Dependencies Found"
echo "========================================"
echo ""
echo "Missing: ${INSTALL_LIST[*]}"
echo ""

# Detect OS and provide installation instructions
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Please install missing dependencies using your package manager:"
    echo ""
    
    INSTALL_COMMANDS=()
    
    # Python installation
    if [[ " ${INSTALL_LIST[@]} " =~ " Python " ]]; then
        if command -v apt-get &> /dev/null; then
            echo "Python 3.11:"
            echo "  sudo apt update"
            echo "  sudo apt install python3.11 python3.11-venv python3.11-pip"
            INSTALL_COMMANDS+=("sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-pip")
        elif command -v dnf &> /dev/null; then
            echo "Python 3.11:"
            echo "  sudo dnf install python3.11"
            INSTALL_COMMANDS+=("sudo dnf install -y python3.11")
        elif command -v pacman &> /dev/null; then
            echo "Python 3.11:"
            echo "  sudo pacman -S python311"
            INSTALL_COMMANDS+=("sudo pacman -S --noconfirm python311")
        elif command -v yum &> /dev/null; then
            echo "Python 3.11:"
            echo "  sudo yum install python3.11"
            INSTALL_COMMANDS+=("sudo yum install -y python3.11")
        fi
        echo ""
    fi
    
    # Git installation
    if [[ " ${INSTALL_LIST[@]} " =~ " Git " ]]; then
        if command -v apt-get &> /dev/null; then
            echo "Git:"
            echo "  sudo apt install git"
            INSTALL_COMMANDS+=("sudo apt install -y git")
        elif command -v dnf &> /dev/null; then
            echo "Git:"
            echo "  sudo dnf install git"
            INSTALL_COMMANDS+=("sudo dnf install -y git")
        elif command -v pacman &> /dev/null; then
            echo "Git:"
            echo "  sudo pacman -S git"
            INSTALL_COMMANDS+=("sudo pacman -S --noconfirm git")
        elif command -v yum &> /dev/null; then
            echo "Git:"
            echo "  sudo yum install git"
            INSTALL_COMMANDS+=("sudo yum install -y git")
        fi
        echo ""
    fi
    
    # Docker installation
    if [[ " ${INSTALL_LIST[@]} " =~ " Docker " ]]; then
        echo "Docker:"
        echo "  Please follow the official Docker installation guide:"
        echo "  https://docs.docker.com/engine/install/"
        echo ""
        echo "  Or use your package manager:"
        if command -v apt-get &> /dev/null; then
            echo "    sudo apt install docker.io docker-compose"
        elif command -v dnf &> /dev/null; then
            echo "    sudo dnf install docker docker-compose"
        elif command -v pacman &> /dev/null; then
            echo "    sudo pacman -S docker docker-compose"
        fi
        echo ""
    fi
    
    # Offer to run installation commands
    if [ ${#INSTALL_COMMANDS[@]} -gt 0 ]; then
        if ! check_sudo; then
            echo "Note: sudo access is required for automatic installation."
            echo "You may be prompted for your password."
            echo ""
        fi
        echo "Would you like to run these installation commands now? (requires sudo)"
        read -p "Install now? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            set +e  # Allow errors during installation
            INSTALL_FAILED=0
            for cmd in "${INSTALL_COMMANDS[@]}"; do
                echo "Running: $cmd"
                if ! eval "$cmd"; then
                    echo "WARNING: Installation command failed: $cmd"
                    INSTALL_FAILED=1
                fi
            done
            set -e  # Re-enable error handling
            
            echo ""
            if [ $INSTALL_FAILED -eq 0 ]; then
                echo "Installation complete! Verifying installations..."
                echo ""
                # Re-run verification
                exec "$0"
            else
                echo "Some installations may have failed. Please check the output above."
                echo "Run ./$SCRIPT_NAME again to verify installation."
            fi
            exit 0
        fi
    fi
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Please install missing dependencies:"
    echo ""
    
    if [[ " ${INSTALL_LIST[@]} " =~ " Python " ]]; then
        if command -v brew &> /dev/null; then
            echo "Python 3.11:"
            echo "  brew install python@3.11"
            echo ""
            read -p "Install Python 3.11 now using Homebrew? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                set +e
                if brew install python@3.11; then
                    echo "Python 3.11 installed successfully!"
                    echo ""
                    echo "Verifying installation..."
                    exec "$0"
                else
                    echo "Failed to install Python 3.11. Please try manually."
                fi
                set -e
            fi
        else
            echo "Python 3.11:"
            echo "  Option 1: Install Homebrew, then: brew install python@3.11"
            echo "  Option 2: Download from https://www.python.org/downloads/"
            echo ""
        fi
    fi
    
    if [[ " ${INSTALL_LIST[@]} " =~ " Git " ]]; then
        if command -v brew &> /dev/null; then
            echo "Git:"
            echo "  brew install git"
            echo ""
            read -p "Install Git now using Homebrew? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                set +e
                if brew install git; then
                    echo "Git installed successfully!"
                    echo ""
                    echo "Verifying installation..."
                    exec "$0"
                else
                    echo "Failed to install Git. Please try manually."
                fi
                set -e
            fi
        else
            echo "Git:"
            echo "  Usually comes with Xcode Command Line Tools"
            echo "  Run: xcode-select --install"
            echo ""
        fi
    fi
    
    if [[ " ${INSTALL_LIST[@]} " =~ " Docker " ]]; then
        if command -v brew &> /dev/null; then
            echo "Docker Desktop:"
            echo "  brew install --cask docker"
            echo ""
            read -p "Install Docker Desktop now using Homebrew? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                set +e
                if brew install --cask docker; then
                    echo "Docker Desktop installed successfully!"
                    echo ""
                    echo "IMPORTANT: Docker Desktop needs to be started manually the first time."
                    echo "Please start Docker Desktop from Applications, then run ./$SCRIPT_NAME again"
                    echo ""
                    echo "Verifying installation..."
                    exec "$0"
                else
                    echo "Failed to install Docker Desktop. Please try manually."
                fi
                set -e
            fi
        else
            echo "Docker Desktop:"
            echo "  Download from: https://www.docker.com/products/docker-desktop"
            echo ""
        fi
    fi
    
else
    echo "Please install the following:"
    echo ""
    echo "Python 3.11: https://www.python.org/downloads/"
    echo "Git: https://git-scm.com/downloads"
    echo "Docker: https://www.docker.com/get-started"
    echo ""
fi

echo ""
echo "After installing, run ./$SCRIPT_NAME again to verify installation."
echo ""
exit 1
