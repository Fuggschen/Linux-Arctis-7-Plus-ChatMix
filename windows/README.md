# Windows ChatMix

This directory contains the Windows rewrite of the original Linux-based ChatMix daemon.

The implementation keeps the same functional idea:
- detect the SteelSeries Arctis headset and poll its USB HID reports
- read the knob position from the dial's interrupt endpoint
- map the dial values into Game/Chat balance
- apply them to Windows audio output targets selected in config.json
- support autostart and headless/background mode

Quick start:

  python windows/chatmix_windows.py --create-sample-config
  python windows/chatmix_windows.py --list-devices
  python windows/chatmix_windows.py --install-autostart
  python windows/chatmix_windows.py --tray

Config file:
- default path on Windows: %APPDATA%\ChatMixWindows\config.json
- keys include game_targets, chat_targets, media_targets, media_level, deadband, and log_path

The app is intentionally structured to mirror the Linux logic while replacing PipeWire and systemd with Windows-compatible equivalents.

