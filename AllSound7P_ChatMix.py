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

# Ver info
""" AllSound version, which allows the chatmix dial on the headset
    to control the system default device, no matter which one
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
            Please note: This program only supports the '7+' or the Nova 7 WoW Edition models.""")
            self.die_gracefully(trigger="Couldn't find arctis7 model")

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
            self.log.info(f"default sink identified as {self.system_default_sink}")
        except Exception as e:
            self.log.warning(f"Could not determine default sink name, using auto: {e}")
            self.system_default_sink = "auto"

        # # attempt to identify an Arctis sink via pactl
        # try:
        #     pactl_short_sinks = os.popen("pactl list short sinks").readlines()
        #     # grab any elements from list of pactl sinks that are Arctis 7
        #     arctis = re.compile('.*[aA]rctis.*7')
        #     arctis_sink = list(filter(arctis.match, pactl_short_sinks))[0] 

        #     # split the arctis line on tabs (which form table given by 'pactl short sinks')
        #     tabs_pattern = re.compile(r'\t')
        #     tabs_re = re.split(tabs_pattern, arctis_sink)

        #     # skip first element of tabs_re (sink's ID which is not persistent)
        #     arctis_device = tabs_re[1]
        #     self.log.info(f"Arctis sink identified as {arctis_device}")
        #     default_sink = arctis_device

        # except Exception as e:
        #     self.log.error("""Something wrong with Arctis definition 
        #     in pactl list short sinks regex matching.
        #     Likely no match found for device, check traceback.
        #     """, exc_info=True)
        #     self.die_gracefully(trigger="No Arctis device match")

        # Destroy virtual sinks if they already existed incase of previous failure:
        try:
            destroy_a7p_game = os.system("pw-cli destroy ChatMix_Game 2>/dev/null")
            destroy_a7p_chat = os.system("pw-cli destroy ChatMix_Chat 2>/dev/null")
            if destroy_a7p_game == 0 or destroy_a7p_chat == 0:
                raise Exception
        except Exception as e:
            self.log.info("""Attempted to destroy old VAC sinks at init but none existed""")

        # Instantiate our virtual sinks - Arctis_Chat and Arctis_Game
        try:
            self.log.info("Creating VACS...")
            os.system("""pw-cli create-node adapter '{ 
                factory.name=support.null-audio-sink 
                node.name=ChatMix_Game 
                node.description="ChatMix Game" 
                media.class=Audio/Sink 
                monitor.channel-volumes=true 
                object.linger=true 
                audio.position=[FL FR]
                }' 1>/dev/null
            """)

            os.system("""pw-cli create-node adapter '{ 
                factory.name=support.null-audio-sink 
                node.name=ChatMix_Chat 
                node.description="ChatMix Chat" 
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
            ChatMix virtual device could not be created""", exc_info=True)
            self.die_gracefully(sink_creation_fail=True, trigger="VAC node adapter")

        #route the virtual sink's L&R channels to the default system output's LR
        try:
            default_sink = self.system_default_sink
            self.log.info("Assigning VAC sink monitors output to default device...")

            os.system(f'pw-link "ChatMix_Game:monitor_FL" '
            f'"{default_sink}:playback_FL" 1>/dev/null')

            os.system(f'pw-link "ChatMix_Game:monitor_FR" '
            f'"{default_sink}:playback_FR" 1>/dev/null')

            os.system(f'pw-link "ChatMix_Chat:monitor_FL" '
            f'"{default_sink}:playback_FL" 1>/dev/null')

            os.system(f'pw-link "ChatMix_Chat:monitor_FR" '
            f'"{default_sink}:playback_FR" 1>/dev/null')

        except Exception as e:
            self.log.error("""Couldn't create the links to 
            pipe LR from VAC to default device""", exc_info=True)
            self.die_gracefully(sink_fail=True, trigger="LR links")
        
        # Store ChatMix sink IDs for volume control
        try:
            wpctl_output = os.popen("wpctl status").read()

            # Extract ChatMix_Game ID
            chatmix_game_match = re.search(r'\s*(\d+)\.\s+ChatMix.*Game', wpctl_output)
            if chatmix_game_match:
                self.chatmix_game_id = chatmix_game_match.group(1)
                self.log.info(f"Found ChatMix_Game (ID: {self.chatmix_game_id})")
            else:
                self.chatmix_game_id = None
                self.log.warning("Could not find ChatMix_Game ID")

            # Extract ChatMix_Chat ID
            chatmix_chat_match = re.search(r'\s*(\d+)\.\s+ChatMix.*Chat', wpctl_output)
            if chatmix_chat_match:
                self.chatmix_chat_id = chatmix_chat_match.group(1)
                self.log.info(f"Found ChatMix_Chat (ID: {self.chatmix_chat_id})")
            else:
                self.chatmix_chat_id = None
                self.log.warning("Could not find ChatMix_Chat ID")

        except Exception as e:
            self.log.warning(f"Could not find ChatMix sink IDs: {e}")
            self.chatmix_game_id = None
            self.chatmix_chat_id = None

    def start_modulator_signal(self):
        """Listen to the USB device for modulator knob's signal 
        and adjust volume accordingly
        """

        self.log.info("Reading modulator USB input started")
        self.log.info("-"*45)
        self.log.info("ChatMix Enabled!")
        self.log.info("-"*45)
        while True:
            try:
                # read the input of the USB signal. Signal is sent in 64-bit interrupt packets.
                # read_input[1] returns value to use for default device volume
                # read_input[2] returns the value to use for virtual device volume
                read_input = self.dev.read(self.addr, 64)
                default_device_volume = read_input[1] / 100.0  # wpctl expects 0.0-1.0
                virtual_device_volume = read_input[2] / 100.0

                # os.system calls to issue the commands directly to wpctl using node IDs
                if self.chatmix_game_id:
                    os.system(f'wpctl set-volume {self.chatmix_game_id} {default_device_volume}')
                if self.chatmix_chat_id:
                    os.system(f'wpctl set-volume {self.chatmix_chat_id} {virtual_device_volume}')
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
        # os.system(f"pactl set-default-sink {self.system_default_sink}")

        # cleanup virtual sinks if they exist
        if  sink_creation_fail == False:
            self.log.info("Destroying virtual sinks...")
            os.system("pw-cli destroy ChatMix_Game 1>/dev/null")
            os.system("pw-cli destroy ChatMix_Chat 1>/dev/null")

        if trigger is not None:
            self.log.info("-"*45)
            self.log.fatal("Failure reason: " + trigger)
            self.log.info("-"*45)
            sys.exit(1)
        else:
            self.log.info("-"*45)
            self.log.info("AllSound ChatMix shut down gracefully... Bye Bye!")
            self.log.info("-"*45)
            sys.exit(0)

# init
if __name__ == '__main__':
    a7pcm_service = Arctis7PlusChatMix()
    a7pcm_service.start_modulator_signal()
