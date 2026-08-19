# Installing Wrenify

Choose your platform for detailed instructions:

## 🐧 Linux (Recommended)

| Distribution | Guide | Difficulty |
|--------------|-------|------------|
| Arch / Manjaro | [ARCH.md](./docs/install/ARCH.md) | ⭐ Easy |
| Ubuntu 22.04+ | [UBUNTU.md](./docs/install/UBUNTU.md) | ⭐ Easy |
| Debian 12+ | [UBUNTU.md](./docs/install/UBUNTU.md) | ⭐⭐ Medium |
| Fedora 38+ | [FEDORA.md](./docs/install/FEDORA.md) | ⭐⭐ Medium |
| Other Linux | Use pip/poetry (see UBUNTU.md as base) | ⭐⭐⭐ Hard |

## 🪟 Windows

| Version | Guide | Difficulty |
|---------|-------|------------|
| Windows 10 (1809+) | [WINDOWS.md](./docs/install/WINDOWS.md) | ⭐⭐ Medium |
| Windows 11 | [WINDOWS.md](./docs/install/WINDOWS.md) | ⭐⭐ Medium |

## 🍎 macOS

Not currently supported. Contributions welcome!

## Quick Install (One-Liner)

**Linux (any distro with Python 3.11+ and ffmpeg):**
```bash
git clone https://github.com/MrRishabThapa/Wrenify && cd Wrenify && poetry install && poetry run wrenify
```

**Windows (PowerShell as Admin):**
```powershell
powershell -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/MrRishabThapa/Wrenify/master/install_windows.ps1 | iex"
```

## Prebuilt Downloads

Get precompiled versions from [Releases](https://github.com/MrRishabThapa/Wrenify/releases):

- **Linux**: `Wrenify-x.x.x-x86_64.AppImage`
- **Windows**: `Wrenify-x.x.x-Setup.exe` (coming soon)

## Common Issues

- **Python not found**: Install Python 3.11+ from your system package manager
- **ffmpeg missing**: Every OS has a package for this
- **pyworld fails to build**: Install C++ compiler
- **Long paths on Windows**: See [WINDOWS.md](./docs/install/WINDOWS.md#step-1-enable-long-path-support)

See platform-specific guides for detailed troubleshooting.