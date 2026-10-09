# Windows ChatMix

This directory contains the Windows-oriented rewrite of the Linux ChatMix daemon.

What is included:
- USB headset detection and dial polling for Arctis 7+ / Nova 7 WOW Edition
- Windows audio endpoint targeting with configurable output devices
- per-channel mapping for Game / Chat / Media
- autostart installation via the Windows Startup folder
- background/tray execution support

Usage:

  python windows/chatmix_windows.py --list-devices
  python windows/chatmix_windows.py --install-autostart
  python windows/chatmix_windows.py --run-in-background
  python windows/chatmix_windows.py --tray

The implementation is intentionally structured to be easier to port and extend than the original Linux-only PipeWire logic.
