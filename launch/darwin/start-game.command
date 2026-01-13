#!/bin/sh
echo "Toontown Ranked: Main Game Launcher"
echo
cd ../../../

# Try to find Python
PYTHON_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python"
    if ! command -v python >/dev/null 2>&1; then
        if [ -f "../PPYTHON_PATH" ]; then
            PYTHON_CMD=$(cat ../PPYTHON_PATH)
        else
            echo "Python not found in PATH and PPYTHON_PATH file not found."
            echo "Please install Python 3.12+ and add it to your PATH."
            exit 1
        fi
    fi
fi

# Run dependency checker
echo "Checking dependencies..."
export CALLED_FROM_LAUNCH_SCRIPT=1
$PYTHON_CMD -m launch.launcher.dependency_checker
if [ $? -ne 0 ]; then
    echo ""
    echo "Dependency check failed. Please install missing dependencies and try again."
    exit 1
fi

# Now use PPYTHON_PATH if it exists, otherwise use the Python we found
if [ -f "../PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat ../PPYTHON_PATH)
else
    export PPYTHON_PATH=$PYTHON_CMD
fi

export SERVICE_TO_RUN=CLIENT
export CALLED_FROM_LAUNCH_SCRIPT=1

$PPYTHON_PATH -m pip install -r requirements.txt
$PPYTHON_PATH -m launch.launcher.launch
sleep 1
