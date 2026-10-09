from __future__ import annotations

import argparse
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
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
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
    parser.add_argument("--tray", action="store_true", help="Run in background mode")
    parser.add_argument("--run-in-background", action="store_true", help="Spawn a background process")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--create-sample-config", action="store_true", help="Write a sample config file")
    return parser


class ChatMixWindowsController:
    CHATMIX_REPORT_ID = 0x45
    VENDOR_ID = 0x1038
    PRODUCT_IDS = [0x220E, 0x227A]  # Arctis 7+ and Nova 7 WOW

    def __init__(self, config: ChatMixConfig):
        self.config = config
        self.log = self._configure_logging()
        self.audio = AudioController(config)
        self.should_stop = False
        self.device = None
        self.last_game = None
        self.last_chat = None

        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except Exception:
            pass

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

        return logger

    def _handle_signal(self, signum, frame):
        self.should_stop = True
        self.log.info("Shutdown requested by signal %s", signum)

    def find_headset(self):
        """Find the Arctis headset using pywinusb (Windows native USB HID)."""
        try:
            import pywinusb.hid as hid

            devices = hid.find_all_hid_devices()
            for device in devices:
                try:
                    # Check if this is a SteelSeries device
                    vendor_id = device.vendor_id
                    product_id = device.product_id
                    
                    if vendor_id == self.VENDOR_ID and product_id in self.PRODUCT_IDS:
                        self.log.info(f"Found SteelSeries headset: {device.product_name} (vendor=0x{vendor_id:04x} product=0x{product_id:04x})")
                        self.device = device
                        return device
                except Exception:
                    continue

            self.log.debug("No supported SteelSeries headset found yet.")
            return None

        except Exception as exc:
            self.log.debug(f"Error scanning HID devices: {exc}")
            return None

    def run_loop(self):
        """Poll the headset for dial input and apply volume mixing."""
        self.log.info("Starting chatmix poll loop.")
        self.log.info(f"Config: game_targets={self.config.game_targets}, chat_targets={self.config.chat_targets}")
        self.log.info(f"Looking for SteelSeries Arctis headset (vendor=0x{self.VENDOR_ID:04x})...")

        while not self.should_stop:
            if self.device is None:
                self.device = self.find_headset()
                if self.device is None:
                    time.sleep(2.0)  # Wait longer before retrying
                    continue

            # Try to open and read from the device
            try:
                if not self.device.is_open():
                    self.device.open()
                    self.log.info("Device opened successfully.")

                # Set up input report callback instead of polling
                # This is more efficient and handles data better
                data = self.device.read(64)
                
                if data is None or len(data) == 0:
                    # No data available, that's OK - just continue waiting
                    time.sleep(0.05)
                    continue

                # Check report ID
                if len(data) > 0 and data[0] != self.CHATMIX_REPORT_ID:
                    # Not the chatmix report, ignore it
                    continue

                # Extract game and chat values from bytes 1 and 2
                if len(data) < 3:
                    continue
                    
                game_value = int(data[1])
                chat_value = int(data[2])

                # Validate ranges
                if not (0 <= game_value <= 100 and 0 <= chat_value <= 100):
                    self.log.debug(f"Out of range values: game={game_value} chat={chat_value}")
                    continue

                # Apply deadband to reduce noise
                if self.last_game is not None and self.last_chat is not None:
                    if (abs(game_value - self.last_game) <= self.config.deadband and 
                        abs(chat_value - self.last_chat) <= self.config.deadband):
                        # Within deadband, skip
                        continue

                # New valid values outside deadband
                self.last_game = game_value
                self.last_chat = chat_value
                self._apply_mix_values(game_value, chat_value)
                self.log.info(f"Applied volumes: game={game_value}% chat={chat_value}%")

            except Exception as exc:
                self.log.warning(f"Error reading from device: {exc}")
                # Device was disconnected or read failed
                if self.device is not None:
                    try:
                        self.device.close()
                    except Exception:
                        pass
                self.device = None
                time.sleep(2.0)

    def _apply_mix_values(self, game_value: int, chat_value: int):
        """Apply the dial values to Windows audio endpoints."""
        if game_value is None or chat_value is None:
            return

        game_vol = max(0.0, min(1.0, game_value / 100.0))
        chat_vol = max(0.0, min(1.0, chat_value / 100.0))

        self.audio.set_volume_for_targets(self.config.game_targets, game_vol)
        self.audio.set_volume_for_targets(self.config.chat_targets, chat_vol)

        if self.config.media_targets:
            self.audio.set_volume_for_targets(self.config.media_targets, self.config.media_level)

    def run(self):
        self.audio.initialize_default_targets()
        self.run_loop()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    try:
        if args.create_sample_config:
            config_path = Path(args.config)
            config = ChatMixConfig()
            config.save(str(config_path))
            print(f"Sample config written to {config_path}")
            return 0

        config = ChatMixConfig.load(args.config)
        config.debug = args.debug or config.debug

        if args.list_devices:
            print("\n=== Audio Devices ===")
            for device in list_audio_devices():
                print(f" - {device}")

            print("\n=== USB HID Devices ===")
            try:
                import pywinusb.hid as hid
                devices = hid.find_all_hid_devices()
                if devices:
                    for dev in devices:
                        try:
                            print(f" - {dev.product_name} (vendor=0x{dev.vendor_id:04x} product=0x{dev.product_id:04x})")
                        except Exception:
                            pass
                else:
                    print("  (No USB HID devices found)")
            except Exception as exc:
                print(f"  Error: {exc}")
            print()
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

        # Default: run the service
        if args.tray:
            print(f"Running in background mode. Logs: {config.log_path}")
        else:
            print(f"ChatMix Windows starting.")
            print(f"Logs: {config.log_path}")
            print()

        controller = ChatMixWindowsController(config)
        controller.run()
        return 0

    except KeyboardInterrupt:
        print("\nShutdown requested.")
        return 0
    except Exception as exc:
        logging.exception(f"Fatal error: {exc}")
        print(f"\nERROR: {exc}")
        print(f"See logs at: {config.log_path if 'config' in locals() else DEFAULT_LOG_PATH}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
Windows ChatMix service for SteelSeries Arctis 7+/Nova 7 WOW Edition

Uses Windows' native USB HID API (via pywinusb) - no libusb required.

Usage:
    ChatMixWindows.exe                      (run service in foreground)
    ChatMixWindows.exe --tray               (run service in background)
    ChatMixWindows.exe --list-devices       (show available devices)
    ChatMixWindows.exe --install-autostart  (add to Windows startup)
    ChatMixWindows.exe --remove-autostart   (remove from Windows startup)
    ChatMixWindows.exe --create-sample-config (generate default config)
"""
