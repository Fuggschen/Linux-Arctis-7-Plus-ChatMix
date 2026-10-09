import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def default_config_path() -> Path:
    if os.name == "nt":
        return Path.home() / "AppData" / "Roaming" / "ChatMixWindows" / "config.json"
    return Path.home() / ".chatmix_windows.json"


@dataclass
class ChatMixConfig:
    debug: bool = False
    vendor_id: int = 0x1038
    product_ids: list[int] = field(default_factory=lambda: [0x220e, 0x227a])
    game_targets: list[str] = field(default_factory=lambda: ["Default", "Headphones"]) 
    chat_targets: list[str] = field(default_factory=lambda: ["Discord", "Teams", "VoiceChat"]) 
    media_targets: list[str] = field(default_factory=lambda: ["Media"]) 
    media_level: float = 0.7
    polling_interval_ms: int = 20
    deadband: int = 3
    tray_mode: bool = False
    log_path: str = str(Path.home() / "AppData" / "Local" / "ChatMixWindows" / "chatmix.log")

    @classmethod
    def load(cls, path: str | None = None):
        target = Path(path) if path else default_config_path()
        if target.exists():
            with target.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return cls(**data)
        cfg = cls()
        cfg.save(str(target))
        return cfg

    def save(self, path: str | None = None):
        target = Path(path) if path else default_config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(self.__dict__, handle, indent=2)


def create_sample_config(path: str | None = None):
    config = ChatMixConfig()
    config.save(path)
    return config
