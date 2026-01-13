FROM python:3.12-slim

# Environment
ENV TZ=America/New_York
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (Panda3D + build tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    libassimp-dev \
    libeigen3-dev \
    libgl1-mesa-dev \
    libharfbuzz-dev \
    libjpeg-dev \
    libode-dev \
    libpng-dev \
    libsquish-dev \
    libssl-dev \
    ca-certificates \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy application source
COPY . .

# Start the server
ENTRYPOINT ["python", "-m", "launch.launcher.launch"]
