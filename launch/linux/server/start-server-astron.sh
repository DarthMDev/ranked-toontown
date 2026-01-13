#!/bin/sh
echo "Toontown Ranked: Astron Launcher"
echo
cd ../../..

# Try to find Python
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=python
else
    echo "Error: Python not found in PATH."
    echo "Please install Python 3.12+ and add it to your PATH."
    exit 1
fi

# Run dependency checker (MongoDB required for Astron)
echo "Checking dependencies..."
export CALLED_FROM_LAUNCH_SCRIPT=1
$PYTHON_CMD -m launch.launcher.dependency_checker --require-mongodb
if [ $? -ne 0 ]; then
    echo ""
    echo "Dependency check failed. Please install missing dependencies and try again."
    exit 1
fi

# Now use PPYTHON_PATH if it exists, otherwise use the Python we found
if [ -f "launch/linux/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/linux/PPYTHON_PATH)
else
    export PPYTHON_PATH=$PYTHON_CMD
fi

$PPYTHON_PATH -m pip install -r requirements.txt
$PPYTHON_PATH launch/launcher/start_astron.py
