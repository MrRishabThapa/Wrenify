# Wrenify on Ubuntu / Debian

Tested on Ubuntu 22.04 LTS and Ubuntu 24.04 LTS.  
Should also work on Debian 12+ and Pop!_OS, Linux Mint, Elementary.

## Requirements

- Ubuntu 22.04+ / Debian 12+ / derivatives
- Python 3.11 or newer
- 8 GB RAM minimum
- 5 GB free disk space

## Installation

### Step 1: Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Python 3.11+

Ubuntu 22.04 ships with Python 3.10. You may need 3.11+:

```bash
# Add deadsnakes PPA (for Python 3.11 on 22.04)
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

For Ubuntu 24.04, use system Python:
```bash
sudo apt install -y python3 python3-venv python3-dev
```

### Step 3: Install System Dependencies

```bash
sudo apt install -y \
    ffmpeg \
    portaudio19-dev \
    libqt6-dev \
    libopencv-dev \
    build-essential \
    git \
    cmake
```

### Step 4: Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3.11 -
# Or: python3 - on Ubuntu 24.04

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
poetry --version
```

### Step 5: Configure Poetry to Use Python 3.11

```bash
poetry env use python3.11
```

### Step 6: Clone and Install Wrenify

```bash
cd ~
git clone https://github.com/MrRishabThapa/Wrenify.git
cd Wrenify
poetry install
```

Takes 10-15 minutes.

### Step 7: Launch

```bash
poetry run wrenify
```

## Ubuntu-Specific Notes

### Snap vs .deb Python

If you have Python via Snap:
```bash
# Remove snap Python
sudo snap remove python3

# Use apt Python instead
sudo apt install python3.11
```

### PulseAudio vs PipeWire

Ubuntu 22.04 uses PulseAudio. Ubuntu 24.04 defaults to PipeWire.

Both work with Wrenify. If audio issues:

```bash
# Check which is running
systemctl --user status pipewire
systemctl --user status pulseaudio

# If neither: install PulseAudio
sudo apt install -y pulseaudio
```

## Troubleshooting

### `python3.11: command not found`

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

### `poetry install` fails on pyworld

```bash
# Install build tools
sudo apt install -y build-essential python3.11-dev

# Retry
poetry install
```

### `poetry install` fails on Qt

```bash
# Install Qt6 dev libs
sudo apt install -y libqt6-dev qt6-base-dev

# Or use PySide6 alternative (larger install)
poetry add PySide6
```

### Webcam not detected

```bash
# Check /dev/video* exists
ls -la /dev/video*

# Add user to video group
sudo usermod -aG video $USER
# Logout and login

# Test webcam
sudo apt install -y cheese
cheese
```

### Mic not detected

```bash
# Install PulseAudio Volume Control
sudo apt install -y pavucontrol
pavucontrol

# Go to "Recording" tab, ensure mic is unmuted
```

## Running on Older Ubuntu (20.04)

Ubuntu 20.04 is old but might work:

```bash
# Install Python 3.11 from deadsnakes
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv python3.11-dev

# ffmpeg may need snap for newer version
sudo snap install ffmpeg

# Rest same as above
```

## Uninstalling

```bash
rm -rf ~/Wrenify
rm -rf ~/.config/wrenify
rm -rf ~/.cache/torch
```