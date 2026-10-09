# Build Instructions for Windows ChatMix

This directory contains build scripts to package the Windows ChatMix rewrite into a single portable `.exe` file.

## Prerequisites

- **Python 3.9 or later** (with pip)
- All dependencies installed from `requirements.txt`

## Quick Build

### On Windows (using Command Prompt):

```cmd
build.bat
```

### On Windows, macOS, or Linux (using PowerShell or Bash):

```bash
python build.py
```

or

```bash
bash build.sh  # Linux/macOS only
```

## Build Process

The build scripts:

1. Check Python version and dependencies
2. Install PyInstaller if not already installed
3. Install all requirements from `requirements.txt`
4. Remove old build artifacts
5. Package the application using PyInstaller
6. Clean up temporary files

## Output

The compiled executable will be located at:

```
dist/ChatMixWindows.exe
```

This is a **single, portable executable** that includes all dependencies and can be run standalone on Windows systems.

## Running the Executable

```bash
# Open the configuration UI
ChatMixWindows.exe --ui

# Run in background/tray mode
ChatMixWindows.exe --tray

# Install autostart (Windows Startup folder)
ChatMixWindows.exe --install-autostart

# Create a sample config file
ChatMixWindows.exe --create-sample-config

# List detected audio and USB devices
ChatMixWindows.exe --list-devices
```

## Distribution

After building, you can distribute `dist/ChatMixWindows.exe` standalone. Users on Windows systems with Python installed can run it directly without needing to clone the repository or install dependencies.

## Troubleshooting

### PyInstaller not found

Manually install it:

```bash
pip install PyInstaller
```

### Missing icon file

If `windows/icon.ico` does not exist, the build scripts will create the executable without an icon. You can add one later using resource editors.

### Build fails with USB/pycaw errors

Ensure all dependencies are properly installed:

```bash
pip install -r requirements.txt
```

## Notes

- The resulting `.exe` will be larger (~50-100 MB) due to bundled Python runtime and dependencies.
- First run may take a few seconds as the application initializes.
- The application requires Windows 7 SP1 or later.
