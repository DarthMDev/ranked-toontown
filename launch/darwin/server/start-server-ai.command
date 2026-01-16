#!/bin/sh
echo "Toontown Ranked: AI Launcher"
echo
cd ../..

# Read PPYTHON_PATH from file
if [ -f "launch/darwin/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/darwin/PPYTHON_PATH)
else
    echo "Error: PPYTHON_PATH file not found at launch/darwin/PPYTHON_PATH"
    exit 1
fi

export SERVICE_TO_RUN=AI
export BASE_CHANNEL=401000000
export MAX_CHANNELS=999999
export STATESERVER=4002
export ASTRON_IP="127.0.0.1:7199"
export EVENTLOGGER_IP="127.0.0.1:7197"
export DISTRICT_NAME="Ranked Realms"

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	echo Checking for valid Panda3D Windows installation...
	$PPYTHON_PATH -m pip install "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-macosx_10_9_universal2.whl"
	$PPYTHON_PATH -m launch.launcher.launch
	sleep 5
done
