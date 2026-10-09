"""Build script for Windows ChatMix portable executable (cross-platform).

This script packages the Windows ChatMix rewrite into a single .exe file using PyInstaller.

Requirements:
    - Python 3.9+
    - PyInstaller: pip install pyinstaller
    - All dependencies in requirements.txt installed

Usage:
    python build.py

Output:
    dist/ChatMixWindows.exe
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _check_python_version():
    if sys.version_info < (3, 9):
        print("ERROR: Python 3.9+ is required.")
        return False
    return True


def _install_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        print("WARNING: PyInstaller not found. Installing...")
        return subprocess.run([sys.executable, "-m", "pip", "install", "PyInstaller"], check=False).returncode == 0


def _install_requirements():
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print(f"WARNING: {req_file} not found.")
        return False

    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
        check=False,
    ).returncode == 0


def _cleanup_old_builds():
    for item in ["build", "dist"]:
        path = Path(item)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    for spec_file in Path(".").glob("*.spec"):
        spec_file.unlink(missing_ok=True)


def _build_executable():
    icon_path = Path(__file__).parent / "windows" / "icon.ico"
    script_path = Path(__file__).parent / "windows" / "chatmix_windows.py"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "ChatMixWindows",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    cmd.extend([
        "--add-data",
        f"{Path('windows').absolute()}{os.pathsep}windows",
        "--collect-all",
        "pycaw",
        "--collect-all",
        "usb",
        "--hidden-import=pycaw.pycaw",
        "--hidden-import=usb.core",
        "--hidden-import=usb.backend",
        "--hidden-import=usb.backend.libusb1",
        str(script_path),
    ])

    return subprocess.run(cmd, check=False).returncode == 0


def main() -> int:
    print("")
    print("========================================")
    print("  ChatMix Windows Build Script")
    print("========================================")
    print("")

    print("[1/5] Checking Python version...")
    if not _check_python_version():
        return 1

    print("")
    print("[2/5] Checking dependencies...")
    if not _install_pyinstaller():
        print("ERROR: Failed to install PyInstaller.")
        return 1

    print("")
    print("[3/5] Installing requirements...")
    if not _install_requirements():
        print("ERROR: Failed to install requirements.")
        return 1

    print("")
    print("[4/5] Removing old build artifacts...")
    _cleanup_old_builds()

    print("")
    print("[5/5] Building executable...")
    if not _build_executable():
        print("ERROR: PyInstaller failed.")
        return 1

    print("")
    print("[6/6] Cleaning up build artifacts...")
    _cleanup_old_builds()

    print("")
    print("========================================")
    print("  Build Complete!")
    print("========================================")
    print("")
    print("Executable created at: dist/ChatMixWindows.exe")
    print("")
    print("Usage:")
    print("  ChatMixWindows.exe --ui              (open configuration UI)")
    print("  ChatMixWindows.exe --tray            (run in background)")
    print("  ChatMixWindows.exe --install-autostart (add to Windows startup)")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
