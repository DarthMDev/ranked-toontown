#!/bin/bash
# Toontown Ranked: Docker Server Launcher

cd "$(dirname "$0")/.." || exit 1

echo "========================================"
echo "  Toontown Ranked - Server Launcher"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    echo "Please run initial-setup.sh first to install dependencies"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "Docker is not running. Attempting to start Docker..."
    echo ""
    
    # Try to start Docker service (Linux)
    if command -v systemctl &> /dev/null; then
        echo "Starting Docker service using systemctl..."
        if sudo systemctl start docker 2>/dev/null; then
            echo "Waiting for Docker to be ready..."
            sleep 2
        fi
    elif command -v service &> /dev/null; then
        echo "Starting Docker service using service command..."
        if sudo service docker start 2>/dev/null; then
            echo "Waiting for Docker to be ready..."
            sleep 2
        fi
    fi
    
    # Try to start Docker Desktop (macOS)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Starting Docker Desktop..."
        if command -v open &> /dev/null; then
            open -a Docker 2>/dev/null || true
            echo "Waiting for Docker Desktop to start (this may take 30-60 seconds)..."
        fi
    fi
    
    # Wait up to 60 seconds for Docker to be ready
    TIMEOUT=60
    ELAPSED=0
    while [ $ELAPSED -lt $TIMEOUT ]; do
        if docker info &> /dev/null; then
            echo "Docker is now running!"
            echo ""
            break
        fi
        sleep 2
        ELAPSED=$((ELAPSED + 2))
        echo -n "."
    done
    echo ""
    
    # Final check
    if ! docker info &> /dev/null; then
        echo "ERROR: Docker failed to start"
        echo ""
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Please start Docker Desktop manually and try again"
        else
            echo "Please start Docker service manually:"
            echo "  sudo systemctl start docker"
            echo "  or"
            echo "  sudo service docker start"
        fi
        exit 1
    fi
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found"
    if [ -f "env.example" ]; then
        echo "Creating .env from env.example..."
        cp env.example .env
        echo "Please edit .env with your configuration"
        read -p "Press Enter to continue..."
    else
        echo "ERROR: env.example not found"
        exit 1
    fi
fi

echo "Starting Toontown Ranked servers in Docker..."
echo "This may take a few minutes on first run..."
echo ""

docker compose up -d

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  Servers started successfully!"
    echo "========================================"
    echo ""
    echo "Services running:"
    docker compose ps
    echo ""
    echo "To view logs: docker compose logs -f"
    echo "To stop servers: docker compose down"
    echo ""
else
    echo ""
    echo "ERROR: Failed to start servers"
    echo "Check the error messages above"
    exit 1
fi
