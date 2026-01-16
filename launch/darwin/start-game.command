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

$PPYTHON_PATH -m pip install -r requirements.txt
echo Checking for valid Panda3D Windows installation...
$PPYTHON_PATH -m pip install "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-macosx_10_9_universal2.whl"
$PPYTHON_PATH -m launch.launcher.launch
sleep 1
