#!/bin/bash
# Toontown Ranked: Game Client Launcher (macOS)

cd "$(dirname "$0")/../../.." || exit 1

echo "========================================"
echo "  Toontown Ranked - Client Launcher"
echo "========================================"
echo ""

# Determine Python command
PYTHON_CMD=""
if [ -f "launch/darwin/PPYTHON_PATH" ]; then
    PYTHON_CMD=$(cat launch/darwin/PPYTHON_PATH)
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '3\.[0-9]+')
    if [ "$PYTHON_VERSION" == "3.11" ]; then
        PYTHON_CMD="python3"
    else
        echo "ERROR: Python 3.11 not found"
        echo "Please run initial-setup.sh first to install dependencies"
        read -p "Press Enter to exit..."
        exit 1
    fi
else
    echo "ERROR: Python not found"
    echo "Please run initial-setup.sh first to install dependencies"
    read -p "Press Enter to exit..."
    exit 1
fi

export SERVICE_TO_RUN=CLIENT

echo "Installing Python dependencies..."
$PYTHON_CMD -m pip install -r requirements.txt --quiet

echo ""
echo "Starting Toontown Ranked client..."
echo ""

$PYTHON_CMD -m launch.launcher.launch

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to start game client"
    read -p "Press Enter to exit..."
    exit 1
fi
