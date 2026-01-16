#!/bin/sh
echo "Toontown Ranked: Main Game Launcher"
echo
export PPYTHON_PATH=$(cat ../PPYTHON_PATH)
export SERVICE_TO_RUN=CLIENT
cd ../../../

$PPYTHON_PATH -m pip install -r requirements.txt
$PPYTHON_PATH -m pip install -r "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-macosx_10_9_universal2.whl"
$PPYTHON_PATH -m launch.launcher.launch
sleep 1
