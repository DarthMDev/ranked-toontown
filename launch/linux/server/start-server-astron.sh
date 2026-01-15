#!/bin/sh
echo "Toontown Ranked: Astron Launcher"
echo
cd ../../..

# Read PPYTHON_PATH from file
if [ -f "launch/linux/PPYTHON_PATH" ]; then
    export PPYTHON_PATH=$(cat launch/linux/PPYTHON_PATH)
else
    echo "Error: PPYTHON_PATH file not found at launch/linux/PPYTHON_PATH"
    exit 1
fi

$PPYTHON_PATH -m pip install -r requirements.txt
$PPYTHON_PATH launch/launcher/start_astron.py
