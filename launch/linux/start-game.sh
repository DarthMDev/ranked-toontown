#!/bin/sh
echo "Toontown Ranked: Main Game Launcher"
echo
export PPYTHON_PATH=$(cat ../PPYTHON_PATH)
export SERVICE_TO_RUN=CLIENT
cd ../../../

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	echo Checking for valid Panda3D Windows installation...
	$PPYTHON_PATH -m pip install "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-linux_x86_64.whl"
	$PPYTHON_PATH -m launch.launcher.launch
	sleep 5
done
