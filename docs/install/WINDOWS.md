# Wrenify on Windows

⚠️ **Windows support is experimental.** Linux is the primary platform.  
Expect longer install times and some manual steps.

## Requirements

- **Windows 10** version 1809 or newer, OR **Windows 11**
- **8 GB RAM** minimum, 16 GB recommended
- **10 GB free disk space** (models + libraries + Python)
- **Administrator access** (for initial install only)
- **Microphone** (built-in laptop mic works)
- **Webcam** (optional, for recording video)
- **Headphones** (STRONGLY recommended)

## Installation

There are TWO options:

### Option A: Auto-Installer (Recommended)

The PowerShell script handles everything.

1. **Open PowerShell as Administrator:**
   - Press `Win + X`
   - Select "Windows PowerShell (Admin)" or "Terminal (Admin)"
   - Click "Yes" on the UAC prompt

2. **Paste and run:**
   ```powershell
   powershell -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/MrRishabThapa/Wrenify/master/install_windows.ps1 | iex"
   ```

3. **Follow prompts** — the script will:
   - Enable long path support
   - Install Chocolatey (package manager)
   - Install Python 3.11
   - Install ffmpeg
   - Install Git
   - Install Visual C++ Build Tools (~1.5 GB, takes 15+ min)
   - Install Poetry
   - Clone Wrenify
   - Install Python dependencies
   - Create desktop shortcut

4. **RESTART your computer** when done (required for long paths)

5. **Launch Wrenify** from the desktop shortcut

Total time: 30-45 minutes (mostly downloading).

### Option B: Manual Install

If auto-installer fails, follow these steps carefully.

#### Step 1: Enable Long Path Support

Windows has a 260-character path limit that breaks Python packages.

**Via PowerShell (Administrator):**
```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**Or via Registry Editor:**
1. Press `Win + R`, type `regedit`, press Enter
2. Navigate to: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem`
3. Right-click empty area → New → DWORD (32-bit) Value
4. Name it: `LongPathsEnabled`
5. Set value to: `1`
6. **RESTART your computer**

#### Step 2: Install Python 3.11

1. Go to https://www.python.org/downloads/
2. Download Python 3.11.x (latest)
3. Run installer
4. **✅ CHECK "Add python.exe to PATH"** (very important!)
5. Click "Install Now"

Verify (open new PowerShell):
```powershell
python --version
# Expected: Python 3.11.x
```

#### Step 3: Install Git

1. Download from https://git-scm.com/download/win
2. Run installer with default settings

Verify:
```powershell
git --version
```

#### Step 4: Install FFmpeg

**Method A: Via Chocolatey (easiest)**

Install Chocolatey first (PowerShell as Admin):
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

Then:
```powershell
choco install ffmpeg -y
```

**Method B: Manual**

1. Download from: https://www.gyan.dev/ffmpeg/builds/
2. Get "ffmpeg-release-essentials.zip"
3. Extract to `C:\ffmpeg`
4. Add to PATH:
   - Search "Environment Variables" in Start
   - Click "Environment Variables"
   - Under "System variables", find "Path", click "Edit"
   - Click "New", add: `C:\ffmpeg\bin`
   - OK, OK, OK
5. Restart PowerShell

Verify:
```powershell
ffmpeg -version
```

#### Step 5: Install Visual C++ Build Tools

Required for compiling pyworld and other C-extension packages.

1. Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Run installer
3. Select workload: **"Desktop development with C++"**
4. Click "Install" (takes 15-20 minutes, ~1.5 GB)

#### Step 6: Install Poetry

Open PowerShell:
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

Add Poetry to PATH:
```powershell
$env:Path += ";$env:APPDATA\Python\Scripts"
```

Make permanent:
1. Search "Environment Variables" in Start
2. Click "Edit environment variables for your account"
3. Find "Path" under User variables → Edit → New
4. Add: `%APPDATA%\Python\Scripts`
5. OK, OK

Restart PowerShell and verify:
```powershell
poetry --version
```

#### Step 7: Clone and Install Wrenify

```powershell
cd $HOME\Documents
git clone https://github.com/MrRishabThapa/Wrenify.git
cd Wrenify
poetry install
```

If this fails on pyworld or torch, try:
```powershell
poetry run pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
poetry install
```

Takes 10-15 minutes.

#### Step 8: Launch Wrenify

```powershell
poetry run wrenify
```

## First-Time Setup

The setup wizard will:

1. Check ffmpeg installation
2. Download Whisper AI model (~75 MB)
3. Create folders
4. Optional: configure API tokens (skip if unsure)

After setup, the app opens.

## Using Wrenify

Same as Linux — see main [README.md](../../README.md) for usage.

## Troubleshooting

### "python is not recognized"

Python not in PATH. Reinstall Python:
- Uninstall existing Python
- Reinstall with ✅ "Add python.exe to PATH" checked

Or manually add to PATH:
- `C:\Users\<YourName>\AppData\Local\Programs\Python\Python311\`
- `C:\Users\<YourName>\AppData\Local\Programs\Python\Python311\Scripts\`

### "poetry: command not found"

```powershell
$env:Path += ";$env:APPDATA\Python\Scripts"
```

Then follow Step 6 to make permanent.

### "Microsoft Visual C++ 14.0 or greater required"

Install Visual C++ Build Tools (Step 5 above).

### `poetry install` hangs forever

Common causes:
1. **Slow internet**: torch is ~2 GB, wait
2. **Bad connection**: cancel with Ctrl+C, retry
3. **Corrupted pip cache**: 
   ```powershell
   poetry cache clear pypi --all
   poetry install
   ```

### Webcam not detected

Windows Settings → Privacy → Camera:
- Enable "Allow apps to access your camera"
- Enable "Allow desktop apps to access your camera"

Restart Wrenify.

### Microphone not working

Windows Settings → Privacy → Microphone:
- Enable "Allow apps to access your microphone"
- Enable "Allow desktop apps to access your microphone"

Also:
- Right-click volume icon in system tray
- Select "Sounds" → Recording tab
- Ensure your mic is set as Default

### "SmartScreen prevented an unrecognized app"

Windows blocks unsigned apps on first launch:
1. Click "More info" on the warning
2. Click "Run anyway"

This won't happen again for this app.

### Import fails with SSL error

```powershell
poetry run pip install --upgrade certifi
```

### Demucs takes forever on Windows

Normal on CPU-only Windows systems:
- 3-minute song: 10-15 minutes
- 5-minute song: 15-25 minutes

**Close browser and heavy apps** during processing for best speed.

### Audio playback stutters

Increase buffer size (advanced):

Edit `wrenify/audio/player.py`:
```python
BLOCK_SIZE: int = 2048  # was 1024
```

### "Path too long" errors

1. Verify long paths enabled (Step 1)
2. Restart computer
3. If still broken: install to shorter path
   ```powershell
   Move-Item $HOME\Documents\Wrenify C:\Wrenify
   cd C:\Wrenify
   poetry install
   ```

## Uninstalling

```powershell
# Remove installation
Remove-Item -Recurse -Force $HOME\Documents\Wrenify

# Remove user data
Remove-Item -Recurse -Force $env:LOCALAPPDATA\Wrenify

# Remove models cache
Remove-Item -Recurse -Force $HOME\.cache\torch
Remove-Item -Recurse -Force $HOME\.cache\huggingface

# Remove desktop shortcut
Remove-Item $HOME\Desktop\Wrenify.lnk
```

## Getting Help

- GitHub Issues: https://github.com/MrRishabThapa/Wrenify/issues
- When reporting bugs, include:
  - Windows version (`winver`)
  - Python version (`python --version`)
  - Full error text
  - Screenshot of the issue