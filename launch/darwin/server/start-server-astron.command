# In macOS to start in the current directory we need to run this command
cd "$(dirname "$0")"
echo "Toontown Ranked: Astron Launcher"
echo
cd ../../../astron

./astrondmac --loglevel info config/astrond.yml
