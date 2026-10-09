#!/bin/bash
# Build script for Windows ChatMix portable executable (Linux/macOS)
# This script packages the Windows ChatMix rewrite into a single .exe file using PyInstaller.
#
# Requirements:
#   - Python 3.9+
#   - PyInstaller: pip install pyinstaller
#   - All dependencies in requirements.txt installed
#
# Usage:
#   bash build.sh
#
# Output:
#   dist/ChatMixWindows.exe

set -e

echo ""
echo "========================================"
echo "  ChatMix Windows Build Script"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH."
    echo "Please install Python 3.9+ and add it to your system PATH."
    exit 1
fi

echo "[1/5] Checking dependencies..."
if ! python3 -m pip show PyInstaller &> /dev/null; then
    echo "WARNING: PyInstaller not found. Installing..."
    python3 -m pip install PyInstaller
fi

echo ""
echo "[2/5] Checking requirements..."
python3 -m pip install -q -r requirements.txt

echo ""
echo "[3/5] Removing old build artifacts..."
rm -rf build dist *.spec 2>/dev/null || true

echo ""
echo "[4/5] Building executable..."
python3 -m PyInstaller --onefile \
    --windowed \
    --name ChatMixWindows \
    --add-data "windows:windows" \
    --collect-all pycaw \
    --collect-all usb \
    --hidden-import=pycaw.pycaw \
    --hidden-import=usb.core \
    --hidden-import=usb.backend \
    --hidden-import=usb.backend.libusb1 \
    windows/chatmix_windows.py

echo ""
echo "[5/5] Cleaning up build artifacts..."
rm -rf build *.spec 2>/dev/null || true

echo ""
echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""
echo "Executable created at: dist/ChatMixWindows.exe"
echo ""
echo "Usage:"
echo "  ChatMixWindows.exe --ui              (open configuration UI)"
echo "  ChatMixWindows.exe --tray            (run in background)"
echo "  ChatMixWindows.exe --install-autostart (add to Windows startup)"
echo ""
