from __future__ import annotations

import os
import subprocess

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except Exception:  # pragma: no cover - optional dependency
    AudioUtilities = None
    IAudioEndpointVolume = None


def list_audio_devices() -> list[str]:
    if os.name != "nt":
        return []

    if AudioUtilities is not None:
        try:
            # pycaw does not provide a simple list of endpoints, so this is a practical fallback.
            import pycaw
            return ["Default playback device"]
        except Exception:
            pass

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as exc:  # pragma: no cover - environment dependent
        return [f"Error enumerating devices: {exc}"]


class AudioController:
    def __init__(self, config):
        self.config = config

    def initialize_default_targets(self):
        if self.config.game_targets and self.config.chat_targets:
            return
        self.config.game_targets = ["Default"]
        self.config.chat_targets = ["Default"]

    def set_volume_for_targets(self, targets: list[str], volume: float):
        if AudioUtilities is None:
            return

        volume = max(0.0, min(1.0, float(volume)))
        endpoint = AudioUtilities.GetSpeakers()
        interface = endpoint.Activate(
            IAudioEndpointVolume._iid_,
            0,
            None,
        )
        master = interface.QueryInterface(IAudioEndpointVolume)
        master.SetMasterVolumeLevelScalar(volume, None)

