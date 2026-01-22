# In macOS to start in the current directory we need to run this command
cd "$(dirname "$0")"
echo "Toontown Ranked: Dedicated Server Launcher"
echo
export PPYTHON_PATH=$(cat ../PPYTHON_PATH)
cd ../../../

export WANT_ERROR_REPORTING="true"

while true
do
	$PPYTHON_PATH -m pip install -r requirements.txt
	$PPYTHON_PATH -m toontown.toonbase.DedicatedServerStart
	sleep 5
done
