# In macOS to start in the current directory we need to run this command
cd "$(dirname "$0")"
echo "Toontown Ranked: AI Launcher"
echo
export PPYTHON_PATH=$(cat ../PPYTHON_PATH)
export SERVICE_TO_RUN=AI
cd ../../..

export BASE_CHANNEL=401000000
export MAX_CHANNELS=999999
export STATESERVER=4002
export ASTRON_IP="127.0.0.1:7199"
export EVENTLOGGER_IP="127.0.0.1:7197"
export DISTRICT_NAME="Ranked Realms"
export WANT_ERROR_REPORTING="true"

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	echo Checking for valid Panda3D installation...
  $PPYTHON_PATH -m pip install "https://github.com/toontown-archipelago/panda3d/releases/latest/download/panda3d-1.11.0-cp311-cp311-macosx_10_9_universal2.whl"
	$PPYTHON_PATH -m launch.launcher.launch
	sleep 5
done
