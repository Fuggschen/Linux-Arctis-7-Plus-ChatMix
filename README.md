# Linux-Arctis-7-Plus-ChatMix

**Now supports both SteelSeries Arctis 7+ and Nova 7 WOW Edition headsets!**

##***Important Licensing Notice**##

`Linux-Arctis-7-Plus-Chatmix` uses the GPL license. While the GPL license does permit commercial use,
it is **strongly discouraged** to reuse the work herein for any for-profit purpose as it relates to the usage
of a third party proprietary hardware device. 

The device itself has not been reverse-engineered for this purpose, nor has the proprietary GG Sonar Software typically
required to use it. 


## Overview
<br>
The SteelSeries Arctis series of headsets include a hardware modulation knob for 'chatmix' on the headset.
This allows the user to 'mix' the volume of two different devices on their system, named "Game" and "Chat".

On older Arctis models (e.g. Arctis 7), the headset would be detected as two individual hardware devices by
the host operating system and would assign them as such accordingly, allowing the user to specify which device to
use and where.

**Typical use case:** "Chat" for voicechat in games and VOIP/comms software, and "Game" for system / music etc.

On newer SteelSeries models like the Arctis 7+ and Nova 7 WOW Edition, this two-device differentiation no longer exists, and the host OS will only recognize a single device.
If the user wishes to utilize the chatmix modulation knob, they *must* install the SteelSeries proprietary GG software. This
software does not currently support Linux.

This script provides a basic workaround for this problem for Linux users. It creates a Virtual Audio Cable (VAC) pair called "Arctis 7+ Chat"
and "Arctis 7+ Game" respectively, which the user can then assign accordingly as they would have done with an older Arctis model.

**Supported Devices:**
- SteelSeries Arctis 7+ (Product ID: 0x220e)
- SteelSeries Nova 7 WOW Edition (Product ID: 0x227a) 
The script listens to the headset's USB dongle signals and interprets them in a way that can be meaningfully converted
to adjust the audio when the user moves the dial on the headset.

### Two Versions ###

`install-a7pcm.sh` installs a daemon which ensures the chatmix dial controls the ChatMix balance on the headset.

Alternatively, use `install-AllSound7P_ChatMix.sh` installs a different version which will control the ChatMix balance
on *any* default system device, e.g. speakers etc.

The daemon is installed as a user systemd service and is enabled to start at boot. You do **not** need to disconnect
and reconnect the dongle to get it running: the service retries every few seconds until the device shows up, so simply
plugging the dongle in is enough. It also recovers on its own if the dongle is unplugged later.

For the AllSound version, ensure the device you wish to output sound to is set as the default device *before* starting
the daemon, since the current default is captured at startup.

For the Arctis version, the headset will be automatically set to the default device when the daemon starts.

<br>

## Requirements
<br>

The service itself depends on the [PyUSB](https://github.com/walac/pyusb) package. Install it with your
distribution's package manager — it must be importable by the system `python3`, since that is the interpreter the
systemd unit runs:

```bash
sudo pacman -S python-pyusb   # Arch
sudo apt install python3-usb  # Debian/Ubuntu
```

The installer checks for this up front and aborts with instructions if it is missing. `libusb` itself is pulled in
as a dependency.

The system requires **PipeWire** with `pw-cli`, `pw-link`, `pw-dump`, and `wpctl` utilities, which are standard on modern Linux systems. 
The script uses native PipeWire commands (`pw-cli`, `pw-link`, `wpctl`) for audio routing and volume control, making it compatible 
with pure PipeWire setups without requiring the PulseAudio compatibility layer.

<br>

## Installation
<br>

Run `install-a7pcm.sh` as your desktop user in the project root directory. You may need to provide your `sudo` password during installation for copying the udev rule for your device.

The installer copies the daemon to `~/.local/bin/`, installs the udev rule, enables linger for your user so the
service starts at boot, and enables + starts `arctis7pcm.service`.

The dongle may stay plugged in throughout. The udev rule is applied to the already-connected device, so there is no
need to disconnect it before installing or reconnect it afterwards.

To uninstall, set the `UNINSTALL` environment variable while calling the install script, e.g.,

```bash
UNINSTALL= ./install-a7pcm.sh
```

Check the service with:

```bash
systemctl --user status arctis7pcm.service
```

<br>

## Service management
<br>

```bash
systemctl --user status arctis7pcm.service    # current state
journalctl --user -u arctis7pcm.service -f    # follow the log
systemctl --user restart arctis7pcm.service   # force a restart
systemctl --user stop arctis7pcm.service      # stop (restores your default sink)
```

The unit is configured to recover rather than stay down:

- `Restart=always` with `RestartSec=5` — the daemon is restarted if it exits, whether it failed or exited cleanly.
  A USB disconnect exits non-zero precisely so that it is restarted once the dongle returns.
- `StartLimitIntervalSec=0` — restart rate limiting is disabled, so the service will never give up permanently. It
  keeps retrying every few seconds, including at boot before your desktop session has started PipeWire.
- `PartOf=pipewire.service` — the virtual sinks do not survive a PipeWire restart, so the service is restarted along
  with it instead of continuing to control node IDs that no longer exist.

Stopping the service is safe: it destroys the virtual sinks and restores your previous default sink.

<br>

## Implementation - How it works
<br>

The service first initializes the VAC by making direct calls to PipeWire's `pw-cli` to create `nodes` and `pw-link` to connect them to the default audio device.

The service relies on the [PyUSB](https://github.com/walac/pyusb) package to read interrupt transfers from the headset's USB dongle.

The headset sends three bytes, the second and third of which are the volume values for the dial's two directions (toward 'Chat' down, toward 'Game' up).

The volumes are processed by the service and passed to the audio system via native PipeWire's `wpctl` command.

The service will automatically set "Arctis 7+ Game" as the default device on startup.

The service supports both the Arctis 7+ and Nova 7 WOW Edition headsets by detecting their respective USB product IDs.

If the dongle is not present — at boot, or after it is unplugged — the daemon exits non-zero and systemd restarts it
every few seconds until the device appears. Each start re-resolves the device, so it also handles the dongle coming
back at a new bus/device path. A USB read error takes the same path rather than exiting cleanly, which is what keeps
the service from staying down after a disconnect.

<br>

# Acknowledgements

With great thanks to:
- [awth13](https://github.com/awth13), especially for contributions in creation of our rules.d and systemd configuration and for wrestling with ALSA in our early attempts
- [Alexandra Zaharia's](https://github.com/alexandra-zaharia) excellent [article](https://alexandra-zaharia.github.io/posts/stopping-python-systemd-service-cleanly) for the clear advice on good practices for sigterm SIGINT/SIGTERM & logging
- [PyUSB's creators](https://github.com/pyusb) for [PyUSB](https://github.com/pyusb/pyusb) itself
- Honorable mention: [this reddit thread for clueing me in to reading the USB input!](https://www.reddit.com/r/steelseries/comments/s4uzos/arctis_7_on_linux_sonar_workaround/hu51jjy/)

