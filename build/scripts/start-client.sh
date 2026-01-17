#!/bin/bash
# Toontown Ranked - Client Launcher for macOS

export SERVICE_TO_RUN=CLIENT
cd game

while true; do
    ./launch
    
    echo ""
    read -p "Game closed. Press Enter to relaunch, or Ctrl+C to exit..."
done