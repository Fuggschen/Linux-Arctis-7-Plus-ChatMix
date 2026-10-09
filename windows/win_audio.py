import os
import subprocess
import sys
from pathlib import Path


def _startup_link_path() -> Path:
    if os.name != "nt":
        raise RuntimeError("Auto-start is only supported on Windows.")
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "ChatMixWindows.lnk"


def install_autostart():
    if os.name != "nt":
        raise RuntimeError("Auto-start is only supported on Windows.")

    script_path = Path(__file__).resolve().parent / "chatmix_windows.py"
    python_path = sys.executable
    target = _startup_link_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    # This uses PowerShell's Shell.Link COM object for a reliable shortcut.
    ps = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('" + str(target) + "'); "
        "$Shortcut.TargetPath = '" + python_path + "'; "
        "$Shortcut.Arguments = '" + str(script_path) + " --tray'; "
        "$Shortcut.WorkingDirectory = '" + str(script_path.parent) + "'; "
        "$Shortcut.Save()"
    ]
    subprocess.run(["powershell", *ps], check=True)
    print(f"Autostart shortcut installed: {target}")


def remove_autostart():
    if os.name != "nt":
        raise RuntimeError("Auto-start is only supported on Windows.")
    target = _startup_link_path()
    if target.exists():
        target.unlink()
        print(f"Removed autostart shortcut: {target}")
    else:
        print("No autostart shortcut found.")
