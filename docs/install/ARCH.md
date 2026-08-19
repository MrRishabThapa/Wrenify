# Wrenify on Arch Linux / Manjaro

Arch is the **primary development platform** — most extensively tested.

## Requirements

- Arch Linux or Manjaro (any recent version)
- 8 GB RAM minimum, 16 GB recommended
- 5 GB free disk space
- Microphone
- Webcam (optional, for recording video)
- Headphones (STRONGLY recommended for karaoke)

## Installation

### Step 1: Install System Dependencies

```bash
sudo pacman -Syu
sudo pacman -S --needed \
    python \
    python-pip \
    ffmpeg \
    portaudio \
    git \
    base-devel
```

### Step 2: Install Poetry

Two options:

**Option A: Via pacman (recommended)**
```bash
sudo pacman -S python-poetry
```

**Option B: Via official installer**
```bash
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc  # or ~/.zshrc
```

Verify:
```bash
poetry --version
```

### Step 3: Clone Wrenify

```bash
cd ~/Projects  # or wherever you want it
git clone https://github.com/MrRishabThapa/Wrenify.git
cd Wrenify
```

### Step 4: Install Python Dependencies

```bash
poetry install
```

Takes 10-15 minutes (downloads torch ~2GB).

### Step 5: Launch Wrenify

```bash
poetry run wrenify
```

First launch runs a 2-5 minute setup wizard.

## Hyprland-Specific Notes

Wrenify works natively on Hyprland/Wayland. No special config needed.

If webcam has issues:
```bash
# Verify webcam accessible
ls /dev/video*

# Add user to video group if needed
sudo usermod -aG video $USER
# Then logout and login again
```

## Uninstalling

```bash
cd ~/Projects
rm -rf Wrenify

# Also remove user config and models
rm -rf ~/.config/wrenify
rm -rf ~/.cache/torch  # Whisper/Demucs models
```

## Troubleshooting

### `poetry install` fails on pyworld

```bash
# Ensure base-devel is installed
sudo pacman -S base-devel
poetry install
```

### `poetry install` fails on Demucs/torch

```bash
# Install torch separately with CPU-only wheel
poetry run pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
poetry install
```

### Webcam permission denied

```bash
sudo usermod -aG video $USER
# Log out and back in
```

### Audio device not detected

```bash
# List audio devices
poetry run python -c "import sounddevice; print(sounddevice.query_devices())"

# Set default input in pavucontrol
sudo pacman -S pavucontrol
pavucontrol
```

### Wayland/Hyprland: PyQt6 doesn't show

Force X11 backend as fallback:
```bash
QT_QPA_PLATFORM=xcb poetry run wrenify
```

## Building AppImage from Source

To create a portable AppImage:

```bash
# Install appimagetool
yay -S appimagetool-bin
# Or download manually: https://github.com/AppImage/AppImageKit/releases

# Build
./build/build_appimage.sh 0.1.0

# Output: dist/Wrenify-0.1.0-x86_64.AppImage
```