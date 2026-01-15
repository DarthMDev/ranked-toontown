#!/bin/sh
echo "Toontown Ranked: Main Game Launcher"
echo
cd ../../../

# Read PPYTHON_PATH from file
if [ -f "launch/darwin/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/darwin/PPYTHON_PATH)
else
    echo "Error: PPYTHON_PATH file not found at launch/darwin/PPYTHON_PATH"
    exit 1
fi

export SERVICE_TO_RUN=CLIENT
export CALLED_FROM_LAUNCH_SCRIPT=1

$PPYTHON_PATH -m pip install -r requirements.txt
$PPYTHON_PATH -m launch.launcher.launch
sleep 1
