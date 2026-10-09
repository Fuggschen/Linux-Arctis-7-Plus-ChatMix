import os
import subprocess
from typing import Iterable


try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except Exception:  # pragma: no cover - optional dependency
    AudioUtilities = None
    IAudioEndpointVolume = None


def list_audio_devices() -> list[str]:
    if os.name != "nt":
        return []

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
        self.default_device_name = config.game_targets[0] if config.game_targets else "Default"

    def initialize_default_targets(self):
        # On Windows, the default audio endpoint is a reasonable target if the user has not specified any names.
        # The selection is stored in the config and can be customized later via JSON.
        if self.config.game_targets:
            return
        self.config.game_targets = ["Default"]
        self.config.chat_targets = ["Default"]

    def set_volume_for_targets(self, targets: Iterable[str], volume: float):
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

        # Some Windows versions allow a default endpoint only. The config therefore represents a target list of
        # friendly names; if the target does not match the active default, the value is still applied to the default endpoint.
        for target in targets:
            if target.lower() in {"default", "speaker", "speakers"}:
                master.SetMasterVolumeLevelScalar(volume, None)
                continue
            # The prototype does not enumerate all endpoints by name; the default endpoint remains the active volume target
            # while allowing the configuration to describe which channels should be driven.
            master.SetMasterVolumeLevelScalar(volume, None)

    def set_master_volume(self, volume: float):
        if AudioUtilities is None:
            return
        endpoint = AudioUtilities.GetSpeakers()
        interface = endpoint.Activate(
            IAudioEndpointVolume._iid_,
            0,
            None,
        )
        master = interface.QueryInterface(IAudioEndpointVolume)
        master.SetMasterVolumeLevelScalar(max(0.0, min(1.0, float(volume))), None)
