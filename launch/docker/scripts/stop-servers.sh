#!/bin/bash
# Toontown Ranked: Stop Docker Servers

cd "$(dirname "$0")/.." || exit 1

echo "========================================"
echo "  Toontown Ranked - Stop Servers"
echo "========================================"
echo ""

docker compose down

if [ $? -eq 0 ]; then
    echo ""
    echo "Servers stopped successfully!"
    echo ""
else
    echo ""
    echo "ERROR: Failed to stop servers"
    exit 1
fi
