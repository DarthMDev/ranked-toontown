#!/bin/sh
echo "Toontown Ranked: Astron Launcher"
echo
cd ../..

# Read PPYTHON_PATH from file
if [ -f "launch/darwin/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/darwin/PPYTHON_PATH)
else
    echo "Error: PPYTHON_PATH file not found at launch/darwin/PPYTHON_PATH"
    exit 1
fi

$PPYTHON_PATH -m pip install -r requirements.txt
$PPYTHON_PATH launch/launcher/start_astron.py
