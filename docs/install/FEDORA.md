# Wrenify on Fedora / RHEL / Rocky

Tested on Fedora 38, 39, and 40.

## Requirements

- Fedora 38+ (or RHEL 9+, Rocky Linux 9+)
- Python 3.11+ (default in Fedora 38+)
- 8 GB RAM
- 5 GB disk

## Installation

### Step 1: Update System

```bash
sudo dnf upgrade --refresh -y
```

### Step 2: Enable RPM Fusion (for ffmpeg)

```bash
sudo dnf install -y https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm

sudo dnf install -y https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
```

### Step 3: Install System Dependencies

```bash
sudo dnf install -y \
    python3.11 \
    python3.11-devel \
    python3-pip \
    ffmpeg \
    portaudio-devel \
    qt6-qtbase-devel \
    opencv \
    gcc \
    gcc-c++ \
    cmake \
    git
```

### Step 4: Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -

export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

poetry --version
```

### Step 5: Clone and Install

```bash
cd ~
git clone https://github.com/MrRishabThapa/Wrenify.git
cd Wrenify
poetry install
```

### Step 6: Launch

```bash
poetry run wrenify
```

## SELinux Notes

Fedora ships with SELinux in enforcing mode. Wrenify should work fine,
but if you hit permission errors:

```bash
# Check for denials
sudo ausearch -m avc -ts recent

# Temporarily set to permissive to test
sudo setenforce 0
poetry run wrenify

# If it works, add a policy exception (advanced) or leave permissive
```

## Troubleshooting

### `dnf` can't find ffmpeg

Enable RPM Fusion (step 2 above). Fedora doesn't ship ffmpeg by default
due to patent concerns.

### `poetry install` fails on OpenCV

```bash
sudo dnf install opencv-devel python3-opencv
poetry install
```

### PipeWire audio issues

Fedora 38+ uses PipeWire natively. Should work but if issues:

```bash
systemctl --user status pipewire-pulse
# Should be "active (running)"

# Restart if needed
systemctl --user restart pipewire pipewire-pulse
```

## Uninstalling

```bash
rm -rf ~/Wrenify
rm -rf ~/.config/wrenify
rm -rf ~/.cache/torch
```