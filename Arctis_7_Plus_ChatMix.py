"""   Copyright (C) 2022  birdybirdonline & awth13 - see LICENSE.md
    @ https://github.com/birdybirdonline/Linux-Arctis-7-Plus-ChatMix
    
    Contact via Github in the first instance
    https://github.com/birdybirdonline
    https://github.com/awth13
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
    """

import os
import sys
import signal
import logging
import traceback
import re
import json
import time
import usb.core

# Set PipeWire runtime directory
if 'PIPEWIRE_RUNTIME_DIR' not in os.environ:
    os.environ['PIPEWIRE_RUNTIME_DIR'] = os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')

def wait_for_pipewire(max_attempts=10, delay=0.5):
    """Wait for PipeWire to become available"""
    for attempt in range(max_attempts):
        try:
            result = os.popen("pw-dump 2>&1").read()
            if result and not "can't connect" in result.lower() and result.strip().startswith('['):
                return True
        except:
            pass
        time.sleep(delay)
    return False


class Arctis7PlusChatMix:
    def __init__(self):

        # set to receive signal from systemd for termination
        signal.signal(signal.SIGTERM, self.__handle_sigterm)

        self.log = self._init_log()
        self.log.info("Initializing ac7pcm...")

        # identify the arctis 7+ device
        try:
            # Support both Arctis 7P (0x220e) and Nova 7 WOW Edition (0x227a)
            self.dev = usb.core.find(idVendor=0x1038, idProduct=0x220e) or \
                        usb.core.find(idVendor=0x1038, idProduct=0x227a)
        except Exception as e:
            self.log.error("""Failed to identify the Arctis 7+ device.
            Please ensure it is connected.\n
            Please note: This program only supports the '7+'  or the Nova 7 WoW Edition models""")
            self.die_gracefully(trigger ="Couldn't find arctis7 model")

        # select its interface and USB endpoint, and capture the endpoint address
        try:
            # interface index 8 of the Arctis 7+ is the USB HID for the ChatMix dial;
            # its actual interface number on the device itself is 5.
            self.interface = self.dev[0].interfaces()[8]
            self.interface_num = self.interface.bInterfaceNumber
            self.endpoint = self.interface.endpoints()[0]
            self.addr = self.endpoint.bEndpointAddress

            self.log.info(f"ChatMix interface: {self.interface_num}, endpoint: {hex(self.addr)}, "
                         f"max packet: {self.endpoint.wMaxPacketSize}")

        except Exception as e:
            self.log.error("""Failure to identify relevant 
            USB device's interface or endpoint. Shutting down...""")
            self.die_gracefully(exc=True, trigger ="identification of USB endpoint")

        # detach if the device is active
        if self.dev.is_kernel_driver_active(self.interface_num):
            self.dev.detach_kernel_driver(self.interface_num)

        self.VAC = self._init_VAC()


    def _init_log(self):
        log = logging.getLogger(__name__)
        log.setLevel(logging.INFO)  # Changed from DEBUG to INFO for production
        stdout_handler = logging.StreamHandler()
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(logging.Formatter('%(levelname)8s | %(message)s'))
        log.addHandler(stdout_handler)    
        return (log)

    def _init_VAC(self):
        """Get name of default sink, establish virtual sink
        and pipe its output to the default sink
        """

        # Wait for PipeWire to be available
        self.log.info("Waiting for PipeWire connection...")
        if not wait_for_pipewire():
            self.log.error("PipeWire is not available after waiting. Check if pipewire.service is running.")
            self.log.error(f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR')}")
            self.log.error(f"PIPEWIRE_RUNTIME_DIR={os.environ.get('PIPEWIRE_RUNTIME_DIR')}")
            self.die_gracefully(trigger="PipeWire not available")

        self.log.info("PipeWire connection established!")

        # get the default sink name using pw-cli
        try:
            pw_dump_output = os.popen("pw-dump 2>&1").read()
            pw_data = json.loads(pw_dump_output)

            # Find default sink
            default_sink_name = None
            default_sink_id = None
            for item in pw_data:
                if item.get("type") == "PipeWire:Interface:Metadata":
                    metadata = item.get("metadata", [])
                    for meta in metadata:
                        if meta.get("key") == "default.audio.sink":
                            default_sink_name = meta.get("value", {}).get("name")
                            break
                    if default_sink_name:
                        break

            # If not found via metadata, get from pw-cli
            if not default_sink_name:
                default_sink_name = os.popen("pw-cli info @DEFAULT_AUDIO_SINK@ 2>/dev/null | grep 'node.name' | cut -d'\"' -f2").read().strip()

            self.system_default_sink = default_sink_name if default_sink_name else "auto"

            # Also get the ID for later restoration
            if default_sink_name:
                wpctl_status = os.popen("wpctl status").read()
                sink_id_match = re.search(rf'\s*(\d+)\.\s+{re.escape(default_sink_name)}', wpctl_status)
                if sink_id_match:
                    self.system_default_sink_id = sink_id_match.group(1)
                else:
                    self.system_default_sink_id = None
            else:
                self.system_default_sink_id = None

            self.log.info(f"default sink identified as {self.system_default_sink}" +
                         (f" (ID: {self.system_default_sink_id})" if self.system_default_sink_id else ""))
        except Exception as e:
            self.log.warning(f"Could not determine default sink name, using auto: {e}")
            self.system_default_sink = "auto"
            self.system_default_sink_id = None

        # attempt to identify an Arctis sink via pw-cli
        try:
            pw_sinks = os.popen("pw-cli list-objects 2>/dev/null | grep -A 20 'type PipeWire:Interface:Node'").read()
            arctis = re.compile('.*[aA]rctis.*7')

            # Look for Arctis device in pw-cli output
            arctis_device = None
            for line in pw_sinks.split('\n'):
                if 'node.name' in line and arctis.search(line):
                    # Extract node name from quotes
                    match = re.search(r'node\.name\s*=\s*"([^"]+)"', line)
                    if match:
                        arctis_device = match.group(1)
                        self.log.info(f"Arctis sink identified as {arctis_device}")
                        break

            if arctis_device:
                default_sink = arctis_device
            else:
                # If no Arctis device found, use system default
                default_sink = self.system_default_sink
                self.log.info("No Arctis device found, using system default sink")

        except Exception as e:
            self.log.warning(f"Could not identify Arctis sink, using system default: {e}")
            default_sink = self.system_default_sink

        # Destroy virtual sinks if they already existed incase of previous failure:
        try:
            destroy_a7p_game = os.system("pw-cli destroy Arctis_Game 2>/dev/null")
            destroy_a7p_chat = os.system("pw-cli destroy Arctis_Chat 2>/dev/null")
            if destroy_a7p_game == 0 or destroy_a7p_chat == 0:
                raise Exception
        except Exception as e:
            self.log.info("""Attempted to destroy old VAC sinks at init but none existed""")

        # Instantiate our virtual sinks - Arctis_Chat and Arctis_Game
        try:
            self.log.info("Creating VACS...")
            os.system("""pw-cli create-node adapter '{ 
                factory.name=support.null-audio-sink 
                node.name=Arctis_Game 
                node.description="Arctis 7+ Game" 
                media.class=Audio/Sink 
                monitor.channel-volumes=true 
                object.linger=true 
                audio.position=[FL FR]
                }' 1>/dev/null
            """)

            os.system("""pw-cli create-node adapter '{ 
                factory.name=support.null-audio-sink 
                node.name=Arctis_Chat 
                node.description="Arctis 7+ Chat" 
                media.class=Audio/Sink 
                monitor.channel-volumes=true 
                object.linger=true 
                audio.position=[FL FR]
                }' 1>/dev/null
            """)

            # Wait for sinks to appear in PipeWire
            time.sleep(0.5)

        except Exception as E:
            self.log.error("""Failure to create node adapter - 
            Arctis_Chat virtual device could not be created""", exc_info=True)
            self.die_gracefully(sink_creation_fail=True, trigger="VAC node adapter")

        #route the virtual sink's L&R channels to the default system output's LR
        try:
            self.log.info("Assigning VAC sink monitors output to default device...")

            os.system(f'pw-link "Arctis_Game:monitor_FL" '
            f'"{default_sink}:playback_FL" 1>/dev/null')

            os.system(f'pw-link "Arctis_Game:monitor_FR" '
            f'"{default_sink}:playback_FR" 1>/dev/null')

            os.system(f'pw-link "Arctis_Chat:monitor_FL" '
            f'"{default_sink}:playback_FL" 1>/dev/null')

            os.system(f'pw-link "Arctis_Chat:monitor_FR" '
            f'"{default_sink}:playback_FR" 1>/dev/null')

        except Exception as e:
            self.log.error("""Couldn't create the links to 
            pipe LR from VAC to default device""", exc_info=True)
            self.die_gracefully(sink_fail=True, trigger="LR links")
        
        # set the default sink to Arctis Game by finding its ID
        try:
            # Get the IDs of Arctis nodes for later use
            wpctl_output = os.popen("wpctl status").read()

            # Extract Arctis_Game ID
            arctis_game_match = re.search(r'\s*(\d+)\.\s+Arctis.*Game', wpctl_output)
            if arctis_game_match:
                self.arctis_game_id = arctis_game_match.group(1)
                os.system(f'wpctl set-default {self.arctis_game_id}')
                self.log.info(f"Set Arctis_Game (ID: {self.arctis_game_id}) as default sink")
            else:
                self.arctis_game_id = None
                self.log.warning("Could not find Arctis_Game ID to set as default")

            # Extract Arctis_Chat ID
            arctis_chat_match = re.search(r'\s*(\d+)\.\s+Arctis.*Chat', wpctl_output)
            if arctis_chat_match:
                self.arctis_chat_id = arctis_chat_match.group(1)
                self.log.info(f"Found Arctis_Chat (ID: {self.arctis_chat_id})")
            else:
                self.arctis_chat_id = None
                self.log.warning("Could not find Arctis_Chat ID")

        except Exception as e:
            self.log.warning(f"Could not set Arctis_Game as default sink: {e}")
            self.arctis_game_id = None
            self.arctis_chat_id = None

    def start_modulator_signal(self):
        """Listen to the USB device for modulator knob's signal 
        and adjust volume accordingly
        """
        
        self.log.info("Reading modulator USB input started")
        self.log.info("-"*45)
        self.log.info("Arctis 7+ ChatMix Enabled!")
        self.log.info("-"*45)

        last_game_vol = None
        last_chat_vol = None

        while True:
            try:
                # read the input of the USB signal. Signal is sent in 64-bit interrupt packets.
                # read_input[1] returns value to use for default device volume
                # read_input[2] returns the value to use for virtual device volume
                read_input = self.dev.read(self.addr, 64, timeout=1000)

                game_val = read_input[1]
                chat_val = read_input[2]

                # Only update if values changed
                if game_val != last_game_vol or chat_val != last_chat_vol:
                    default_device_volume = game_val / 100.0  # wpctl expects 0.0-1.0
                    virtual_device_volume = chat_val / 100.0

                    # os.system calls to issue the commands directly to wpctl using node IDs
                    if self.arctis_game_id:
                        os.system(f'wpctl set-volume {self.arctis_game_id} {default_device_volume}')
                    if self.arctis_chat_id:
                        os.system(f'wpctl set-volume {self.arctis_chat_id} {virtual_device_volume}')

                    last_game_vol = game_val
                    last_chat_vol = chat_val
            except usb.core.USBTimeoutError:
                pass
            except usb.core.USBError:
                self.log.fatal("USB input/output error - likely disconnect")
                break

    def __handle_sigterm(self, sig, frame):
        self.die_gracefully()

    def die_gracefully(self, sink_creation_fail=False, trigger=None):
        """Kill the process and remove the VACs
        on fatal exceptions or SIGTERM / SIGINT
        """
        
        self.log.info('Cleanup on shutdown')
        # Restore system default sink if we have an ID
        if hasattr(self, 'system_default_sink_id') and self.system_default_sink_id:
            os.system(f"wpctl set-default {self.system_default_sink_id}")
        elif hasattr(self, 'system_default_sink') and self.system_default_sink != "auto":
            # Fallback: try to find ID by name
            wpctl_status = os.popen("wpctl status").read()
            sink_id_match = re.search(rf'\s*(\d+)\.\s+{re.escape(self.system_default_sink)}', wpctl_status)
            if sink_id_match:
                os.system(f"wpctl set-default {sink_id_match.group(1)}")

        # cleanup virtual sinks if they exist
        if  sink_creation_fail == False:
            self.log.info("Destroying virtual sinks...")
            os.system("pw-cli destroy Arctis_Game 1>/dev/null")
            os.system("pw-cli destroy Arctis_Chat 1>/dev/null")

        if trigger is not None:
            self.log.info("-"*45)
            self.log.fatal("Failure reason: " + trigger)
            self.log.info("-"*45)
            sys.exit(1)
        else:
            self.log.info("-"*45)
            self.log.info("Artcis 7+ ChatMix shut down gracefully... Bye Bye!")
            self.log.info("-"*45)
            sys.exit(0)

# init
if __name__ == '__main__':
    a7pcm_service = Arctis7PlusChatMix()
    a7pcm_service.start_modulator_signal()
