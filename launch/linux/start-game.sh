#!/bin/sh
echo "Toontown Ranked: Main Game Launcher"
echo
cd ../../../

# Read PPYTHON_PATH from file
if [ -f "launch/linux/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/linux/PPYTHON_PATH)
else
    echo "Error: PPYTHON_PATH file not found at launch/linux/PPYTHON_PATH"
    exit 1
fi

export SERVICE_TO_RUN=CLIENT

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	export CALLED_FROM_LAUNCH_SCRIPT=1
	$PPYTHON_PATH -m launch.launcher.launch
	sleep 5
done
