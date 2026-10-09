from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _startup_link_path() -> Path:
    if os.name != "nt":
        raise RuntimeError("Autostart is only supported on Windows.")
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "ChatMixWindows.lnk"


def install_autostart(config_path: str | None = None) -> Path:
    if os.name != "nt":
        raise RuntimeError("Autostart is only supported on Windows.")

    config_target = Path(config_path) if config_path else Path.home() / "AppData" / "Roaming" / "ChatMixWindows" / "config.json"
    script_path = Path(__file__).resolve().parent / "chatmix_windows.py"
    python_exe = sys.executable
    shortcut_path = _startup_link_path()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    powershell = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path}'); "
            f"$Shortcut.TargetPath = '{python_exe}'; "
            f"$Shortcut.Arguments = '"{script_path}" --tray --config "{config_target}"'; "
            f"$Shortcut.WorkingDirectory = '{script_path.parent}'; "
            "$Shortcut.Save()"
        ),
    ]

    subprocess.run(["powershell", *powershell], check=True)
    print(f"Autostart shortcut created at: {shortcut_path}")
    return shortcut_path


def remove_autostart() -> None:
    if os.name != "nt":
        raise RuntimeError("Autostart is only supported on Windows.")

    shortcut_path = _startup_link_path()
    if shortcut_path.exists():
        shortcut_path.unlink()
        print(f"Removed autostart shortcut: {shortcut_path}")
    else:
        print("No autostart shortcut found.")

