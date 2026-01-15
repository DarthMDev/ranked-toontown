#!/bin/sh
echo "Toontown Ranked: UD Launcher"
echo
cd ../..

# Read PPYTHON_PATH from file
if [ -f "launch/darwin/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/darwin/PPYTHON_PATH)
else
    echo "Error: PPYTHON_PATH file not found at launch/darwin/PPYTHON_PATH"
    exit 1
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
