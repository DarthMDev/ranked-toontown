# Ranked Toontown
Welcome to the Ranked Toontown repository! This modded Toontown client/server is the successor to
`TT-CL-Edition` (Toontown: Crane League Edition) and has a heavy focus on competitive craning, with features such as a ranked ELO system, and standardized RNG within the crane round. The craning also **almost perfectly** emulates the craning changes made in Corporate Clash's 1.2.8 update, which is considered to be the competitive standard for the craning community. 

Let me reiterate, this source is designed to **emulate** Clash gameplay specifically in the crane round. We are not trying to steal clash's ideas, gameplay, or anything of that nature. 

This source has quite the history, so I will try to break it down really quick.

This source is built off of [Toontown: Archipelago](https://github.com/toontown-archipelago/toontown-archipelago), as it is by far the **best** publically available offline source to make modifications to. 

Toontown: Archipelago was built off of `TT-CL-Edition`, as there was lots of quality of life additions already added such as custom keybinds, orbital camera, and most importantly, Corporate Clash's 1.2.8 craning mechanics.

`TT-CL-Edition` was built on the foundation of Toontown Offline's Toontown School House's source code.
Toontown School House is a course dedicated to teaching members of the Toontown community how to develop for the game. For more information, head over to [this](https://www.reddit.com/r/Toontown/comments/doszgg/toontown_school_house_learn_to_develop_for/) Reddit post.

This modded version of the game also contains a lot of fun additions that are meant to spice up boss round gameplay, but there is a **heavy** focus on the crane round.

# Source Code
This source code is based on a March 2019 fork of Toontown Offline v1.0.0.0 used for Toontown School House. It has been stripped of all Toontown Offline exclusive features, save one. The brand new Magic Words system made for Toontown Offline has been left alone, and upgraded to the most recent build. This feature will allow users to easily navigate around Toontown without any hassle.

On top of that, this source code has also been updated to Python 3, utilizing a more modern version of Panda3D. 

Credits:
* **The Toontown Offline Team** for the foundation of this codebase (Toontown Schoolhouse)
* [The Corporate Clash Crew](https://corporateclash.net) for toon models, some various textures, and assistance with implementing v1.2.8 craning
* **Polygon** for making the Corporate Clash toon models
* [Open Toontown](https://github.com/open-toontown) for providing a great reference for a Toontown codebase ported to Python 3 and the HD Mickey Font
* [Astron](https://github.com/Astron/Astron)
* [Panda3D](https://github.com/panda3d/panda3d)
* [libotp-nametags](https://github.com/loblao/libotp-nametags)
* Reverse-engineered Toontown Online client/server source code is property of The Walt Disney Company.

# Getting Started

Toontown Ranked uses Docker to run all server components (MongoDB, Astron, Uberdog, AI), making setup much simpler. The game client runs locally on your machine.

## Quick Start

### Step 1: Run the Installation Wizard

Before starting, run the setup wizard to check and install all required dependencies:

**Windows:**
```batch
cd launch\docker
initial-setup.bat
```

**Linux/macOS:**
```bash
cd launch/docker
chmod +x initial-setup.sh
./initial-setup.sh
```

**Note:** These scripts work even if Python isn't installed yet! They will:
- Check if Python 3.11 is installed
- If not, help you install it automatically (Windows) or provide instructions (Linux/macOS)
- Once Python is installed, run the full setup wizard

The wizard will check for and help install:
- Python 3.11
- Git
- Docker
- WSL2 (Windows only - required for Docker Desktop)

**Note:** Docker Desktop will automatically install WSL2 and the "Virtual Machine Platform" feature if needed. Hyper-V is NOT required when using the WSL2 backend (which is the default).

### Step 2: Start the Servers

Navigate to `launch/docker/scripts/` and run the server launcher:

**Windows:**
```batch
cd launch\docker\scripts
start-servers.bat
```

**Linux/macOS:**
```bash
cd launch/docker/scripts
chmod +x *.sh *.command  # First time only
./start-servers.sh
```

This will start all server components in Docker containers. The first time may take a few minutes to download and build the containers.

### Step 3: Start the Game Client

Once the servers are running, launch the game client:

**Windows:**
```batch
start-game.bat
```

**Linux:**
```bash
./start-game.sh
```

**macOS:**
```bash
./start-game.command
```

### Step 4: Choose Your Server

When the game launches, you'll be prompted to choose:
- **Public Server**: Connect to the official Toontown Ranked server
- **Other Server**: Connect to a custom server (localhost or remote)

## Stopping the Servers

To stop the Docker servers:

**Windows:**
```batch
cd launch\docker\scripts
stop-servers.bat
```

**Linux/macOS:**
```bash
cd launch/docker/scripts
./stop-servers.sh
```

## Important Notes

- **Docker is required** to run the game servers. The setup wizard will help you install it.
- **Python 3.11** is required for the game client.
- All server components (MongoDB, Astron, Uberdog, AI) run inside Docker containers.
- The game client runs locally on your machine.
- **No MongoDB installation needed** - it's included in the Docker setup!

## Configuration

If you need to customize server settings, edit `launch/docker/.env` (created automatically from `env.example`).

### Legacy Installation (Advanced Users)

For advanced users who want to run servers without Docker, see [Running From Source.](#running-from-source)

# Running from source (Advanced)

**Note:** For most users, we recommend using the [Docker-based setup](#getting-started) above. This section is for advanced users who want to run servers without Docker.

## Requirements

### Python 3.11
This source requires Python 3.11. **Ensure that you add Python to your PATH during installation.**

### Panda3D
This source can be run using any modern version of Panda3D. It is highly recommended that you don't install Panda3D as it is installed automatically as a pip dependency. If you have issues launching the source, it is **more than likely** that you have a Python PATH conflict. If this occurs, the simplest solution is to **uninstall all instances of Panda3D and Python** on your computer, reinstall Python 3.11, and try again.

### MongoDB
**MongoDB is required** to run Toontown Ranked without Docker. You can install it manually from [mongodb.com](https://www.mongodb.com/try/download/community). Make sure MongoDB is added to your system PATH.

## Starting the game

### Option 1: Using Batch Files
Please navigate to the `/launch` directory, then your platform:
- Windows: `/windows`
- Mac: `/darwin`
- Linux: `/linux`

Then run the following scripts in order:
- `/server/start_astron_server`
- `/server/start_uberdog_server`
- `/server/start_ai_server`
- `./start_game`

### Option 2: Using PyCharm/IDE (For Developers)
You can launch directly from PyCharm by running `launch/launcher/launch.py`:
1. Set the `SERVICE_TO_RUN` environment variable to `AI`, `UD`, or `CLIENT`
2. Run `launch.py`

## Common Issues/FAQ
### I set up the server and everything is running fine. I can connect to my own server but my friends can't. Why?
If you are hosting a Mini-Server, you **must** port forward to allow incoming connections on port `7198`.
There are two ways to accomplish this:
- Port forward the port `7198` in your router's settings.
- Use a third party program (such as Hamachi) to emulate a LAN connection over the internet.

As router settings are wildly different, I cannot provide a tutorial on how to do this on this README for your specific router. However, the process is pretty straight forward assuming you have access to your router's settings.  You should be able to figure it out with a bit of research on Google.


### I launched the game and I am getting the error: The system cannot find the path specified
There are multiple reasons that can cause this to occur. If you continue to have problems:

1. **Check PPYTHON_PATH:** Ensure the `PPYTHON_PATH` file exists in `launch/windows/` (or `launch/linux/` or `launch/darwin/` for other platforms) and contains the correct Python command.

2. **Manual installation:** If Python is not found:
   - Uninstall all instances of Python from your system
   - Download Python 3.11 from [python.org](https://www.python.org/downloads/)
   - During installation, **ensure "Add Python to PATH" is checked**
   - Restart your computer and try again

3. **Still having issues?** Feel free to ask any of the contributors in the Discord for assistance
**Technical Note:** The launcher automatically detects the correct Python installation and saves it to `PPYTHON_PATH`. If you're technically savvy and want to manually configure this, ensure your `PPYTHON_PATH` file contains the path to your Python 3.11 installation

### I logged in and I have no gags and can't go anywhere.... why can't I play?
This game is specifically designed for minigames on the Trolley, with a heavy focus on the crane round. That's it. That's the entire game.

### I was playing and my game crashed :(
Ranked Toontown is currently in an early alpha build so many issues are expected to be present. If you found a crash/bug, feel free to [create an Issue](https://github.com/ranked-toontown/ranked-toontown/issues/new) on the GitHub page for the repository. Developers/contributors use this as a "todo list". If you choose to do this, try and be as descriptive as possible on what caused the crash, and any sort of possible steps that can be taken to reproduce it.


### I was playing and the district reset :(
Similarly to a game crash, sometimes the district can crash. Follow the same steps as the previous point.