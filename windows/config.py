import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import ChatMixConfig, default_config_path
from .win_audio import AudioController


DEFAULT_LOG_PATH = Path.home() / "AppData" / "Local" / "ChatMixWindows" / "chatmix.log"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows ChatMix controller for Arctis 7+/Nova 7 WOW")
    parser.add_argument("--config", type=str, default=str(default_config_path()), help="Path to config JSON file")
    parser.add_argument("--list-devices", action="store_true", help="List available output devices and USB HID devices")
    parser.add_argument("--install-autostart", action="store_true", help="Install startup shortcut")
    parser.add_argument("--remove-autostart", action="store_true", help="Remove startup shortcut")
    parser.add_argument("--tray", action="store_true", help="Run in tray/background mode")
    parser.add_argument("--run-in-background", action="store_true", help="Run headless with no console window")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser


class ChatMixWindowsController:
    CHATMIX_REPORT_ID = 0x45
    VOLUME_DEADBAND = 3

    def __init__(self, config: ChatMixConfig):
        self.config = config
        self.log = self._configure_logging()
        self.audio = AudioController(config)

        self.device = None
        self.endpoint_address = None
        self.last_game = None
        self.last_chat = None
        self.should_stop = False

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _configure_logging(self):
        logger = logging.getLogger("chatmix_windows")
        logger.setLevel(logging.DEBUG if self.config.debug else logging.INFO)
        logger.handlers.clear()

        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        log_path = Path(self.config.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        return logger

    def _handle_signal(self, signum, frame):
        self.log.info("Received shutdown signal %s; stopping controller", signum)
        self.should_stop = True

    def find_headset(self):
        try:
            import usb.core
            candidates = []
            for product_id in self.config.product_ids:
                dev = usb.core.find(idVendor=self.config.vendor_id, idProduct=product_id)
                if dev is not None:
                    candidates.append(dev)
            if not candidates:
                return None
            self.device = candidates[0]
            self.log.info("Headset USB device found: %s", self.device)
            return self.device
        except Exception as exc:  # pragma: no cover - environment dependent
            self.log.exception("Failed to access USB devices: %s", exc)
            return None

    def attach_to_hid_endpoint(self):
        if self.device is None:
            return False

        try:
            self.device.set_configuration()
            for config in self.device:
                for interface in config:
                    if hasattr(interface, "endpoints"):
                        endpoints = interface.endpoints()
                        if endpoints:
                            self.endpoint_address = endpoints[0].bEndpointAddress
                            self.log.info("Using endpoint 0x%02x for headset HID", self.endpoint_address)
                            return True
            self.log.warning("No USB HID endpoint discovered for headset")
            return False
        except Exception as exc:  # pragma: no cover - environment dependent
            self.log.exception("Unable to claim headset USB interface: %s", exc)
            return False

    def _apply_mix_values(self, game_value: int, chat_value: int):
        if game_value is None or chat_value is None:
            return

        self.audio.set_volume_for_targets(self.config.game_targets, game_value / 100.0)
        self.audio.set_volume_for_targets(self.config.chat_targets, chat_value / 100.0)

        if self.config.media_targets:
            self.audio.set_volume_for_targets(self.config.media_targets, self.config.media_level)

    def run_loop(self):
        if not self.find_headset():
            self.log.warning("No supported Arctis headset found; waiting for device to appear")

        # Retry until device shows up, similar to the Linux service behavior.
        while not self.should_stop:
            if self.device is None:
                self.device = self.find_headset()
                if self.device is not None:
                    self.attach_to_hid_endpoint()
                time.sleep(2)
                continue

            try:
                import usb.core
                data = self.device.read(self.endpoint_address, 64, timeout=750)
                if len(data) == 0:
                    continue

                # The Linux code uses the first byte as report ID; only chatmix packets should be processed.
                if data[0] != self.CHATMIX_REPORT_ID:
                    continue

                game_value = int(data[1])
                chat_value = int(data[2])
                if not (0 <= game_value <= 100 and 0 <= chat_value <= 100):
                    continue

                if self.last_game is not None and self.last_chat is not None:
                    if abs(game_value - self.last_game) <= self.VOLUME_DEADBAND and abs(chat_value - self.last_chat) <= self.VOLUME_DEADBAND:
                        continue

                self.last_game = game_value
                self.last_chat = chat_value
                self._apply_mix_values(game_value, chat_value)
                self.log.debug("Game=%s Chat=%s", game_value, chat_value)

            except usb.core.USBTimeoutError:
                # Normal: no input yet.
                continue
            except usb.core.USBError:
                self.log.warning("USB device disconnected; waiting for reconnection")
                self.device = None
                self.endpoint_address = None
                time.sleep(2)
            except Exception as exc:  # pragma: no cover - environment dependent
                self.log.exception("Unhandled USB polling error: %s", exc)
                time.sleep(1)

    def run(self):
        self.audio.initialize_default_targets()
        self.run_loop()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    config = ChatMixConfig.load(args.config)
    config.debug = args.debug or config.debug

    if args.list_devices:
        from .win_audio import list_audio_devices
        print("Audio devices:")
        for name in list_audio_devices():
            print(f" - {name}")
        print("\nUSB HID devices:")
        try:
            import usb.core
            for dev in usb.core.find(find_all=True):
                try:
                    print(f" - {hex(dev.idVendor)}:{hex(dev.idProduct)}")
                except Exception:
                    pass
        except Exception as exc:
            print(f"Unable to enumerate USB devices: {exc}")
        return 0

    if args.install_autostart:
        from .autostart import install_autostart
        install_autostart()
        return 0

    if args.remove_autostart:
        from .autostart import remove_autostart
        remove_autostart()
        return 0

    if args.run_in_background:
        if os.name != "nt":
            print("Background execution is only supported on Windows.")
            return 1
        subprocess.Popen([
            sys.executable,
            str(Path(__file__).resolve().parent / "chatmix_windows.py"),
            "--tray",
            "--config",
            args.config,
        ], creationflags=subprocess.CREATE_NO_WINDOW)
        return 0

    controller = ChatMixWindowsController(config)
    controller.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
