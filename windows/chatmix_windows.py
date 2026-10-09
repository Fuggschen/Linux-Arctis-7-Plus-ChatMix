from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    from .config import ChatMixConfig, default_config_path
    from .win_audio import AudioController, list_audio_devices
except ImportError:  # pragma: no cover - direct script execution on Windows
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    from config import ChatMixConfig, default_config_path
    from win_audio import AudioController, list_audio_devices


DEFAULT_LOG_PATH = Path.home() / "AppData" / "Local" / "ChatMixWindows" / "chatmix.log"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Windows ChatMix controller for SteelSeries Arctis 7+/Nova 7 WOW Edition"
    )
    parser.add_argument("--config", type=str, default=str(default_config_path()), help="Path to config JSON")
    parser.add_argument("--list-devices", action="store_true", help="List audio and USB devices")
    parser.add_argument("--install-autostart", action="store_true", help="Install a Windows Startup shortcut")
    parser.add_argument("--remove-autostart", action="store_true", help="Remove the Startup shortcut")
    parser.add_argument("--tray", action="store_true", help="Run in tray/background mode")
    parser.add_argument("--run-in-background", action="store_true", help="Spawn a background process")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--create-sample-config", action="store_true", help="Write a sample config file")
    return parser


class ChatMixWindowsController:
    CHATMIX_REPORT_ID = 0x45
    POLL_TIMEOUT_MS = 750

    def __init__(self, config: ChatMixConfig):
        self.config = config
        self.log = self._configure_logging()
        self.audio = AudioController(config)
        self.should_stop = False
        self.device = None
        self.endpoint_address = None
        self.last_game = None
        self.last_chat = None

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _configure_logging(self):
        logger = logging.getLogger("chatmix_windows")
        logger.setLevel(logging.DEBUG if self.config.debug else logging.INFO)
        logger.handlers.clear()

        log_path = Path(self.config.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        return logger

    def _handle_signal(self, signum, frame):
        self.should_stop = True
        self.log.info("Shutdown requested by signal %s", signum)

    def find_headset(self):
        try:
            import usb.core

            for product_id in self.config.product_ids:
                dev = usb.core.find(idVendor=self.config.vendor_id, idProduct=product_id)
                if dev is not None:
                    self.device = dev
                    self.log.info("Found supported SteelSeries headset: vendor=0x%04x product=0x%04x", self.config.vendor_id, product_id)
                    return dev

            self.log.warning("No supported headset found yet.")
            return None
        except Exception as exc:  # pragma: no cover - environment dependent
            self.log.exception("Unable to enumerate USB devices: %s", exc)
            return None

    def attach_to_hid_endpoint(self):
        if self.device is None:
            return False

        try:
            self.device.set_configuration()
            for cfg in self.device:
                for interface in cfg:
                    endpoints = getattr(interface, "endpoints", lambda: [])()
                    if endpoints:
                        self.endpoint_address = endpoints[0].bEndpointAddress
                        self.log.info("Using HID endpoint 0x%02x", self.endpoint_address)
                        return True

            self.log.warning("No USB HID endpoint discovered for this headset.")
            return False
        except Exception as exc:  # pragma: no cover - environment dependent
            self.log.exception("Unable to claim USB endpoint: %s", exc)
            return False

    def apply_mix_values(self, game_value: int, chat_value: int):
        if game_value is None or chat_value is None:
            return

        game_vol = max(0.0, min(1.0, game_value / 100.0))
        chat_vol = max(0.0, min(1.0, chat_value / 100.0))

        self.audio.set_volume_for_targets(self.config.game_targets, game_vol)
        self.audio.set_volume_for_targets(self.config.chat_targets, chat_vol)

        # Keep the media target at a fixed background level instead of changing it with the dial.
        if self.config.media_targets:
            self.audio.set_volume_for_targets(self.config.media_targets, self.config.media_level)

    def run_loop(self):
        self.log.info("Starting chatmix poll loop.")

        while not self.should_stop:
            if self.device is None:
                self.device = self.find_headset()
                if self.device is not None:
                    self.attach_to_hid_endpoint()
                time.sleep(1.0)
                continue

            if self.endpoint_address is None:
                if not self.attach_to_hid_endpoint():
                    self.device = None
                    time.sleep(1.0)
                    continue

            try:
                import usb.core

                data = self.device.read(self.endpoint_address, 64, timeout=self.POLL_TIMEOUT_MS)
                if not data or len(data) < 3:
                    continue

                if data[0] != self.CHATMIX_REPORT_ID:
                    continue

                game_value = int(data[1])
                chat_value = int(data[2])

                if not (0 <= game_value <= 100 and 0 <= chat_value <= 100):
                    continue

                if self.last_game is not None and self.last_chat is not None:
                    if abs(game_value - self.last_game) <= self.config.deadband and abs(chat_value - self.last_chat) <= self.config.deadband:
                        continue

                self.last_game = game_value
                self.last_chat = chat_value
                self.apply_mix_values(game_value, chat_value)
                self.log.debug("Applied game=%s chat=%s", game_value, chat_value)

            except usb.core.USBTimeoutError:
                continue
            except usb.core.USBError:
                self.log.warning("Headset disconnected; waiting for re-attach.")
                self.device = None
                self.endpoint_address = None
                time.sleep(2.0)
            except Exception as exc:  # pragma: no cover - environment dependent
                self.log.exception("Unhandled polling error: %s", exc)
                time.sleep(1.0)

    def run(self):
        self.audio.initialize_default_targets()
        self.run_loop()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.create_sample_config:
        config_path = Path(args.config)
        config = ChatMixConfig()
        config.save(str(config_path))
        print(f"Sample config written to {config_path}")
        return 0

    config = ChatMixConfig.load(args.config)
    config.debug = args.debug or config.debug

    if args.list_devices:
        print("Audio devices:")
        for device in list_audio_devices():
            print(f" - {device}")

        try:
            import usb.core
            print("\nUSB devices:")
            for dev in usb.core.find(find_all=True):
                try:
                    print(f" - vendor=0x{dev.idVendor:04x} product=0x{dev.idProduct:04x}")
                except Exception:
                    pass
        except Exception as exc:
            print(f"Unable to enumerate USB devices: {exc}")
        return 0

    if args.install_autostart:
        from autostart import install_autostart
        install_autostart(args.config)
        return 0

    if args.remove_autostart:
        from autostart import remove_autostart
        remove_autostart()
        return 0

    if args.run_in_background:
        if os.name != "nt":
            print("Background execution is only supported on Windows.")
            return 1

        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--tray",
                "--config",
                args.config,
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=False,
        )
        print("Background process spawned.")
        return 0

    if args.tray:
        print("Tray/background mode: running headless.")
        controller = ChatMixWindowsController(config)
        controller.run()
        return 0

    controller = ChatMixWindowsController(config)
    controller.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Windows usage examples:
#   python windows/chatmix_windows.py --create-sample-config
#   python windows/chatmix_windows.py --list-devices
#   python windows/chatmix_windows.py --install-autostart
#   python windows/chatmix_windows.py --run-in-background
#   python windows/chatmix_windows.py --tray

"""
This is a Windows rewrite of the original Linux PipeWire-based ChatMix service.
It keeps the same fundamental concept (read headset dial, adjust game/chat mix values)
but targets the Windows audio stack instead of PipeWire.
"""
