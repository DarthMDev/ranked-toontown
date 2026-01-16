#!/bin/sh
echo "Toontown Ranked: Dedicated Server Launcher"
echo
export PPYTHON_PATH=$(cat ../PPYTHON_PATH)
cd ../../../

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	$PPYTHON_PATH -m toontown.toonbase.DedicatedServerStart
	sleep 5
done
