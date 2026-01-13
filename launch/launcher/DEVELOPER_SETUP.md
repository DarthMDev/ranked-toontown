# Developer Setup Guide

This guide explains how to configure PyCharm (or other IDEs) to run the game services directly.

## Overview

When running from PyCharm, you bypass the launch scripts (`.bat`/`.sh` files) that handle dependency checking. The `launch.py` file will automatically check dependencies when run directly, but you can configure it to be less strict for development.

## PyCharm Run Configurations

### 1. Client Configuration

**Script path:** `launch/launcher/launch.py`

**Environment variables:**
```
SERVICE_TO_RUN=CLIENT
```

**Optional (Developer Mode):**
```
SKIP_DEPENDENCY_CHECK=1
```
or
```
DEVELOPER_MODE=1
```

### 2. AI Server Configuration

**Script path:** `launch/launcher/launch.py`

**Environment variables:**
```
SERVICE_TO_RUN=AI
BASE_CHANNEL=401000000
MAX_CHANNELS=999999
STATESERVER=4002
DISTRICT_NAME=Ranked Realms
ASTRON_IP=127.0.0.1:7199
EVENTLOGGER_IP=127.0.0.1:7197
WANT_ERROR_REPORTING=true
```

**Optional (Developer Mode):**
```
SKIP_DEPENDENCY_CHECK=1
```
or
```
DEVELOPER_MODE=1
```

### 3. UberDOG Server Configuration

**Script path:** `launch/launcher/launch.py`

**Environment variables:**
```
SERVICE_TO_RUN=UD
BASE_CHANNEL=1000000
MAX_CHANNELS=999999
STATESERVER=4002
ASTRON_IP=127.0.0.1:7199
EVENTLOGGER_IP=127.0.0.1:7197
WANT_ERROR_REPORTING=true
```

**Optional (Developer Mode):**
```
SKIP_DEPENDENCY_CHECK=1
```
or
```
DEVELOPER_MODE=1
```

## Dependency Checking Modes

### Regular Mode (Default)
- Full dependency check with prompts
- Blocks launch if Python 3.12+ is missing
- Blocks launch if MongoDB is missing (for AI/UD servers)
- Prompts for installation if dependencies are missing

### Developer Mode (`DEVELOPER_MODE=1`)
- Quiet dependency check (no prompts)
- Warns about missing dependencies but doesn't block
- Allows you to continue even if dependencies are missing
- Useful for developers who know their environment

### Skip Check (`SKIP_DEPENDENCY_CHECK=1`)
- Completely skips dependency checking
- Fastest startup
- Use only if you're certain all dependencies are installed

## Running Services in Order

When running services separately (not using singleplayer mode), start them in this order:

1. **Astron** - Message Director (runs from `astron/astrond.exe` or similar)
2. **UberDOG** - Account and game services
3. **AI** - Game logic server
4. **Client** - Game client

## Notes

- The launch scripts (`.bat`/`.sh`) automatically set `CALLED_FROM_LAUNCH_SCRIPT=1` to prevent duplicate checks
- When running from PyCharm, dependency checks will run automatically unless you set `SKIP_DEPENDENCY_CHECK=1`
- MongoDB is required for AI and UD servers in production, but can be skipped in developer mode
- For singleplayer mode, MongoDB is automatically used if available (no configuration needed)
