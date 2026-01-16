# Docker Launch Scripts

This directory contains scripts to launch Toontown Ranked using Docker for server components.

## Scripts

### Starting the Game

1. **Start Servers** (required first):
   - Windows: `start-servers.bat`
   - Linux/macOS: `start-servers.sh`
   - This starts MongoDB, Astron, Uberdog, and AI servers in Docker containers

2. **Start Game Client**:
   - Windows: `start-game.bat`
   - Linux: `start-game.sh`
   - macOS: `start-game.command`
   - This launches the game client on your local machine

### Stopping the Game

To stop the Docker servers:
- Windows: `stop-servers.bat`
- Linux/macOS: `stop-servers.sh`

## First Time Setup

Before using these scripts:

1. Run `initial-setup.bat` (Windows) or `initial-setup.sh` (Linux/macOS) from `launch/docker/` to check/install dependencies:
   ```bash
   cd launch/docker
   ./initial-setup.sh  # or initial-setup.bat on Windows
   ```

2. Configure your `.env` file in `launch/docker/` (will be created automatically from `env.example`)

3. Make sure Docker is running on your system

## Usage

### Windows
```batch
# Start servers
cd launch\docker\scripts
start-servers.bat

# Wait for servers to start, then start the game
start-game.bat
```

### Linux/macOS
```bash
# Make scripts executable (first time only)
chmod +x launch/docker/scripts/*.sh
chmod +x launch/docker/scripts/*.command

# Start servers
cd launch/docker/scripts
./start-servers.sh

# Wait for servers to start, then start the game
./start-game.sh  # or ./start-game.command on macOS
```

## Troubleshooting

### Servers won't start
- Make sure Docker is running
- Check `.env` file configuration
- View logs: `docker compose logs -f` (from `launch/docker/`)

### Client won't start
- Make sure Python 3.11 is installed
- Make sure servers are running first
- Check that all Python dependencies are installed

### Port conflicts
If port 7198 is already in use, you'll need to:
1. Stop the conflicting service
2. Or modify `docker-compose.yml` to use a different port
