#!/bin/sh
echo "Toontown Ranked: UD Launcher"
echo
cd ../..

# Try to find Python
PYTHON_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python"
    if ! command -v python >/dev/null 2>&1; then
        if [ -f "PPYTHON_PATH" ]; then
            PYTHON_CMD=$(cat PPYTHON_PATH)
        else
            echo "Python not found in PATH and PPYTHON_PATH file not found."
            echo "Please install Python 3.12+ and add it to your PATH."
            exit 1
        fi
    fi
fi

# Run dependency checker (MongoDB required for server)
echo "Checking dependencies..."
export CALLED_FROM_LAUNCH_SCRIPT=1
$PYTHON_CMD -m launch.launcher.dependency_checker --require-mongodb
if [ $? -ne 0 ]; then
    echo ""
    echo "Dependency check failed. Please install missing dependencies and try again."
    exit 1
fi

# Now use PPYTHON_PATH if it exists, otherwise use the Python we found
if [ -f "PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat PPYTHON_PATH)
else
    export PPYTHON_PATH=$PYTHON_CMD
fi

export SERVICE_TO_RUN=UD
export BASE_CHANNEL=1000000
export MAX_CHANNELS=999999
export STATESERVER=4002
export ASTRON_IP="127.0.0.1:7199"
export EVENTLOGGER_IP="127.0.0.1:7197"
export WANT_ERROR_REPORTING="true"

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	export CALLED_FROM_LAUNCH_SCRIPT=1
	$PPYTHON_PATH -m launch.launcher.launch
	sleep 5
done
