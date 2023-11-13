try:
    import indigo
except ImportError:
    pass
import asyncore
import json
import time
import logging
import requests
import threading
import os
from datetime import datetime

import Resources.CONSTANTS as CONST
import Resources.MLCONFIG as MLCONFIG
import Resources.MLGW_CLIENT as MLGW
import Resources.MLCLI_CLIENT as MLCLI
import Resources.BLHIP_CLIENT as BLHIP
import Resources.MLtn_CLIENT as MLtn
import Resources.ASBridge as ASBridge


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # Instantiate an AppleScriptBridge MusicController for N.MUSIC control of apple Music
        self.iTunes = ASBridge.MusicController()

    def startup(self):
        # Get path to plugin config file
        self.path = os.path.abspath(os.getcwd())[:-54] + \
               "Preferences/Plugins/uk.co.lukes_plugins.BeoGateway.plugin.indiPref"

        # If plugin is configured, initialise all clients and set config flag to True
        if os.path.exists(self.path):
            self.configure_clients()
            self.configured = True
        else:
            self.configured = False

    def triggerStartProcessing(self, trigger):
        self.triggers.append(trigger)

    def getDeviceStateList(self, dev):
        stateList = indigo.PluginBase.getDeviceStateList(self, dev)

        if stateList is not None:
            if dev.deviceTypeId in self.devicesTypeDict and dev.deviceTypeId == u"AVrenderer":
                # Add dynamic states onto stateList for devices of type AV renderer
                # This allows devices to have unique source lists, rather than sharing a common source list
                try:
                    sources = dev.pluginProps['sources']
                    for source_name in sources:
                        stateList.append(
                            {
                                "Disabled": False,
                                "Key": "source." + source_name,
                                "StateKey": sources[source_name]['source'],
                                "StateLabel": "Source is " + source_name,
                                "TriggerLabel": "Source is " + source_name,
                                "Type": 50
                            }
                        )
                except KeyError:
                    indigo.server.log("Device " + dev.name + " does not have state key 'sources'\n",
                                      level=logging.WARNING)
                    pass
        return stateList

    def deviceStartComm(self, dev):
        dev.stateListOrDisplayStateIdChanged()

    def __del__(self):
        indigo.PluginBase.__del__(self)

    # ########################################################################################
    # ##### Indigo UI menu constructors
    @staticmethod
    def zonelistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = [("*", "All"), ("Main", "Main")]
        for room in CONST.rooms:
            if (room['Zone'], room['Zone']) not in myarray:
                myarray.append((room['Zone'], room['Zone']))
        return myarray

    @staticmethod
    def roomlistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = [("99", "Any")]
        for room in CONST.rooms:
            myarray.append((room['Room_Number'], room['Room_Name']))
        return myarray

    @staticmethod
    def roomlistgenerator2(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = [("*", "All"), ("global", "global")]
        for room in CONST.rooms:
            myarray.append((room['Room_Name'], room['Room_Name']))
        return myarray

    @staticmethod
    def keylistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = []
        for item in CONST.beo4_commanddict.items():
            myarray.append(item)
        return myarray

    @staticmethod
    def keylistgenerator2(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = []
        for item in CONST.beoremoteone_keydict.items():
            myarray.append(item)
        return myarray

    @staticmethod
    def beo4sourcelistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = []
        for item in CONST.beo4_srcdict.items():
            myarray.append(item)
        return myarray

    @staticmethod
    def beo4sourcelistgenerator2(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = [('Any Source', 'Any Source'), ('Any Audio', 'Any Audio'), ('Any Video', 'Any Video')]
        for item in CONST.beo4_srcdict.items():
            myarray.append(item)
        return myarray

    @staticmethod
    def br1sourcelistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = []
        for item in CONST.available_sources:
            myarray.append(item)
        return myarray

    @staticmethod
    def destinationlistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = []
        for item in CONST.destselectordict.items():
            myarray.append(item)
        return myarray

    @staticmethod
    def srcactivitylistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = [(0x00, "Unknown")]
        for item in CONST.sourceactivitydict.items():
            if item not in myarray:
                myarray.append(item)
        return myarray

    @staticmethod
    def hiptypelistgenerator(filter="", valuesDict=None, typeId="", targetId=0):
        myarray = []
        for item in CONST.blgw_devtypes.items():
            myarray.append(item)
        return myarray

    def playlistgenerator(self, filter="", valuesDict=None, typeId="", targetId=0):
        return self.iTunes.get_playlist_names()

    # ########################################################################################
    # ##### Indigo UI Prefs
    def set_login(self, ui):
        # If LogIn data is updated in config, update the values in the plugin
        self.user = ui.get('userID')
        self.pwd = ui.get('password')
        indigo.server.log("BeoGateway device login details updated!", level=logging.DEBUG)

    def set_gateway(self, ui):
        # If gateway network address data is updated in config, update the values in the plugin
        self.host = ui.get('address')
        self.port = [int(ui.get('mlgw_port')),
                     int(ui.get('hip_port')),
                     23]  # Telnet port - 23
        indigo.server.log("BeoGateway device network address details updated!", level=logging.DEBUG)

    def set_trackmode(self, ui):
        # If Track Mode setting is updated in config, update the value in the plugin
        self.trackmode = ui.get("trackMode")
        indigo.server.log("Track reporting set to " + str(self.trackmode), level=logging.DEBUG)

    def set_verbose(self, ui):
        # If Verbose Mode setting is updated in config, update the value in the plugin
        self.verbose = ui.get("verboseMode")
        indigo.server.log("Verbose Mode set to " + str(self.verbose), level=logging.DEBUG)

    def set_notifymode(self, ui):
        # If Notify Mode setting is updated in config, update the value in the plugin
        self.notifymode = ui.get("notifyMode")
        indigo.server.log("Notification Mode set to " + str(self.notifymode), level=logging.DEBUG)

    def set_debug(self, ui):
        # If Debug Mode setting is updated in config, update the value in the plugin
        self.debug = ui.get("debugMode")

        # Set the debug flag for the clients
        self.mlcli.debug = self.debug
        self.mlgw.debug = self.debug
        if self.mlcli.isBLGW:
            self.blgw.debug = self.debug
        else:
            self.mltn.debug = self.debug

        # Report the debug flag change
        indigo.server.log("Debug Mode set to " + str(self.debug), level=logging.DEBUG)

    def set_music_control(self, ui):
        # If Apple Music Control setting is updated in config, update the value in the plugin
        self.itunes_control = ui.get("iTunesControl")
        self.itunes_source = ui.get("iTunesSource")

        if self.itunes_control:
            indigo.server.log("Apple Music Control enabled on source: " + str(self.itunes_source), level=logging.DEBUG)
        else:
            indigo.server.log("Apple Music Control set to " + str(self.itunes_control), level=logging.DEBUG)

    def set_default_audio(self, ui):
        # Define default audio source for AVrenderers
        self.default_audio_source = ui.get("defaultAudio")
        indigo.server.log("Default Audio Source set to " + str(self.default_audio_source), level=logging.DEBUG)

    def set_playlist_default(self, ui):
        self.playlist_default = ui.get("playlist_default")
        indigo.server.log("Default Apple Music Playlist set to " + str(self.playlist_default), level=logging.DEBUG)

    def set_playlist_green(self, ui):
        self.playlist_green = ui.get("playlist_green")
        indigo.server.log("Green Key Apple Music Playlist set to " + str(self.playlist_green), level=logging.DEBUG)

    def set_playlist_yellow(self, ui):
        self.playlist_yellow = ui.get("playlist_yellow")
        indigo.server.log("Yellow Key Music Playlist set to " + str(self.playlist_yellow), level=logging.DEBUG)

    def set_playlist_red(self, ui):
        self.playlist_red = ui.get("playlist_red")
        indigo.server.log("Red Key Music Playlist set to " + str(self.playlist_red), level=logging.DEBUG)

    def set_playlist_blue(self, ui):
        self.playlist_blue = ui.get("playlist_blue")
        indigo.server.log("Blue Key Music Playlist set to " + str(self.playlist_blue), level=logging.DEBUG)

    # ########################################################################################
    # ##### Indigo UI Actions
    def send_beo4_key(self, action, device):
        device_id = int(device.address)
        key_code = int(action.props.get("keyCode", 0))
        destination = int(action.props.get("destination", 0))
        link = int(action.props.get("linkcmd", 0))
        if destination == 0x06:
            self.mlgw.send_beo4_cmd(device_id, destination, key_code, 0x01, link)
        else:
            self.mlgw.send_beo4_cmd(device_id, destination, key_code, 0x00, link)

    def send_beo4_src(self, action, device):
        device_id = int(device.address)
        key_code = int(action.props.get("keyCode", 0))
        destination = int(action.props.get("destination", 0))
        link = int(action.props.get("linkcmd", 0))
        if destination == 0x06:
            self.mlgw.send_beo4_cmd(device_id, destination, key_code, 0x01, link)
        else:
            self.mlgw.send_beo4_cmd(device_id, destination, key_code, 0x00, link)

    def send_br1_key(self, action, device):
        device_id = int(device.address)
        key_code = int(action.props.get("keyCode", 0))
        network_bit = int(action.props.get("netBit", 0))
        self.mlgw.send_beoremoteone_cmd(device_id, key_code, network_bit)

    def send_br1_src(self, action, device):
        device_id = int(device.address)
        key_code = str(action.props.get("keyCode", 0))
        network_bit = int(action.props.get("netBit", 0))
        try:
            key_code = CONST.beoremoteone_commanddict.get(key_code)
            self.mlgw.send_beoremoteone_select_source(device_id, key_code[0], key_code[1], network_bit)
        except KeyError:
            pass

    def send_hip_cmd(self, action):
        zone = str(action.props.get("zone", 0))
        room = str(action.props.get("room", 0))
        device_type = str(action.props.get("devType", 0))
        device_id = str(action.props.get("deviceID", 0))
        hip_command = str(action.props.get("hip_cmd", 0))
        telegram = "c " + zone + "/" + room + "/" + device_type + "/" + device_id + "/" + hip_command
        if self.mlcli.isBLGW:
            self.blgw.send_cmd(telegram)

    def send_hip_cmd2(self, action):
        hip_command = str(action.props.get("hip_cmd", 0))
        if self.mlcli.isBLGW:
            self.blgw.send_cmd(hip_command)

    def send_hip_query(self, action):
        zone = str(action.props.get("zone", 0))
        room = str(action.props.get("room", 0))
        device_type = str(action.props.get("devType", 0))
        device_id = str(action.props.get("deviceID", 0))
        if self.mlcli.isBLGW:
            self.blgw.query(zone, room, device_type, device_id)

    def send_bnr(self, action):
        cmd_type = str(action.props.get("cmd_type", 0))
        command = str(action.props.get("bnr_cmd", 0))
        cmd_data = str(action.props.get("cmd_data", 0))
        header = ''     # {'Content-Type': 'application/json'}

        try:
            if cmd_type == "GET":
                response = requests.get(url=command, headers=header, timeout=1)
            elif cmd_type == "POST":
                response = requests.post(url=command, headers=header, data=cmd_data, timeout=1)
            if cmd_type == "PUT":
                response = requests.put(url=command, headers=header, data=cmd_data, timeout=1)
            else:
                response = ''

            if response.content:
                response = json.loads(response.content)
                indigo.server.log(json.dumps(response, indent=4), level=logging.DEBUG)
        except requests.ConnectionError as e:
            indigo.server.log("Unable to process BeoNetRemote Command - " + str(e), level=logging.ERROR)

    def request_state_update(self, action, device):
        action_id = str(action.props.get("id", 0))
        zone = str(device.pluginProps['zone'])
        room = str(device.pluginProps['room'])
        device_type = "AV renderer"
        device_id = str(device.name)
        if self.mlcli.isBLGW:
            self.blgw.query(zone, room, device_type, device_id)

    def send_virtual_button(self, action):
        button_id = int(action.props.get("buttonID", 0))
        button_action = int(action.props.get("action", 0))
        self.mlgw.send_virtualbutton(button_id, button_action)

    def post_notification(self, action):
        title = str(action.props.get("title", 0))
        body = str(action.props.get("body", 0))
        self.iTunes.notify(body, title)

    def all_standby(self, action):
        self.mlgw.send_beo4_cmd(1, CONST.CMDS_DEST.get("ALL PRODUCTS"), CONST.BEO4_CMDS.get("STANDBY"))

    def request_serial_number(self):
        self.mlgw.get_serial()

    def request_device_update(self):
        if self.mlcli.isBLGW:
            self.blgw.query(dev_type="AV renderer")

    def reset_clients(self):
        self.check_connection(self.mlgw)
        self.check_connection(self.mlcli)

        if self.mlcli.isBLGW:
            self.check_connection(self.blgw)
        else:
            self.check_connection(self.mltn)

    # ########################################################################################
    # ##### Indigo UI Events
    def light_key(self, message):
        room = message['room_number']
        key_code = CONST.BEO4_CMDS.get(message['command'].upper())

        for trigger in self.triggers:
            props = trigger.globalProps["uk.co.lukes_plugins.BeoGateway.plugin"]
            if trigger.pluginTypeId == "lightKey" and \
                    (props["room"] == str(99) or props["room"] == str(room)) and \
                    props["keyCode"] == str(key_code):
                indigo.server.log("Executing Trigger: " + trigger.name, level=logging.DEBUG)
                indigo.trigger.execute(trigger)
                break

    def control_key(self, message):
        room = message['room_number']
        key_code = CONST.BEO4_CMDS.get(message['command'].upper())

        for trigger in self.triggers:
            props = trigger.globalProps["uk.co.lukes_plugins.BeoGateway.plugin"]
            if trigger.pluginTypeId == "controlKey" and \
                    (props["room"] == str(99) or props["room"] == str(room)) and \
                    props["keyCode"] == str(key_code):
                indigo.server.log("Executing Trigger: " + trigger.name, level=logging.DEBUG)
                indigo.trigger.execute(trigger)
                break

    def beo4_key(self, message):
        source = message['State_Update']['source']
        source_type = message['State_Update']['source']
        key_code = CONST.BEO4_CMDS.get(message['State_Update']['command'].upper())

        for trigger in self.triggers:
            props = trigger.globalProps["uk.co.lukes_plugins.BeoGateway.plugin"]
            if trigger.pluginTypeId == "beo4Key" and props["keyCode"] == str(key_code):
                if props["sourceType"] == "Any Source":
                    indigo.trigger.execute(trigger)
                    break
                elif props["sourceType"] == "Any Audio" and "AUDIO" in source_type:
                    indigo.trigger.execute(trigger)
                    break
                elif props["sourceType"] == "Any Audio" and "AUDIO" in source_type:
                    indigo.trigger.execute(trigger)
                    break
                elif props["sourceType"] == source:
                    indigo.trigger.execute(trigger)
                    break

    def virtual_button(self, message):
        button_id = message['button']
        action = message['action']
        for trigger in self.triggers:
            props = trigger.globalProps["uk.co.lukes_pugins.mlgw.plugin"]
            if trigger.pluginTypeId == "virtualButton" and \
                    props["buttonID"] == str(button_id) and \
                    props["action"] == str(action):
                indigo.trigger.execute(trigger)
                break

    # ########################################################################################
    # ##### Indigo UI Device Controls
    def actionControlDevice(self, action, node):
        """ Callback Method to Control a Relay Device. """
        if node.deviceTypeId == u"AVrenderer":
            if action.deviceAction == indigo.kDeviceAction.TurnOn:
                self._dev_on(node)
            elif action.deviceAction == indigo.kDeviceAction.TurnOff:
                self._dev_off(node)
            elif action.deviceAction == indigo.kDeviceAction.Toggle:
                if node.states["onOffState"]:
                    self._dev_off(node)
                else:
                    self._dev_on(node)
            elif action.deviceAction == indigo.kDeviceAction.RequestStatus:
                self._status_request(node)

    def _dev_on(self, node):
        indigo.server.log(node.name + " turned On")

        # Get a local copy of the gateway states from server
        active_renderers = self.gateway.states['AudioRenderers']
        active_source = self.gateway.states['currentAudioSource']
        active_sourceName = self.gateway.states['currentAudioSourceName']

        if self.debug:
            indigo.server.log('Active renderers: ' + active_renderers, level=logging.DEBUG)
            indigo.server.log('Active Audio Source: ' + active_source, level=logging.DEBUG)

        # Join if music already playing
        if active_renderers != '' and active_source != 'Unknown':
            # Send Beo4 command
            source = active_source
            self.mlgw.send_beo4_cmd(
                int(node.address),
                int(CONST.CMDS_DEST.get("AUDIO SOURCE")),
                int(CONST.BEO4_CMDS.get(source))
            )

            # Update device states
            sourceName = active_sourceName
            key_value_list = [
                {'key': 'onOffState', 'value': True},
                {'key': 'playState', 'value': 'Play'},
                {'key': 'source', 'value': sourceName},
                {'key': 'mute', 'value': False},
            ]

            if self.debug:
                indigo.server.log(
                    node.name + " joining current audio experience " + sourceName + " (" + source +
                    "). Joining active renderer(s): " + active_renderers,
                    level=logging.DEBUG
                )

        # Otherwise start default music source
        else:
            # Send Beo4 command
            source = self.default_audio_source
            self.mlgw.send_beo4_cmd(
                int(node.address),
                int(CONST.CMDS_DEST.get("AUDIO SOURCE")),
                int(CONST.BEO4_CMDS.get(source))
            )

            # Update device states
            sourceName = dict(CONST.available_sources).get(self.default_audio_source)
            key_value_list = [
                {'key': 'onOffState', 'value': True},
                {'key': 'playState', 'value': 'Play'},
                {'key': 'source', 'value': sourceName},
                {'key': 'mute', 'value': False},
            ]

            if self.debug:
                indigo.server.log(
                    node.name + " starting audio experience " + sourceName + " (" + source + ").",
                    level=logging.DEBUG
                )

        # Update states on server
        node.updateStatesOnServer(key_value_list)
        node.updateStateImageOnServer(indigo.kStateImageSel.AvPlaying)

        # Add device to active renderers lists and update gateway
        self.add_to_renderers_list(node.name, 'Audio')
        key_value_list = [
            {'key': 'currentAudioSource', 'value': source},
            {'key': 'currentAudioSourceName', 'value': sourceName},
        ]
        self.gateway.updateStatesOnServer(key_value_list)

    def _dev_off(self, node):
        indigo.server.log(node.name + " turned Off")

        # Send Beo4 command
        self.mlgw.send_beo4_cmd(
            int(node.address),
            int(CONST.CMDS_DEST.get("AUDIO SOURCE")),
            int(CONST.BEO4_CMDS.get('STANDBY'))
        )

        # Update states to standby values
        node.updateStatesOnServer(CONST.standby_state)
        node.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

        # Remove device from active renderers lists
        self.remove_from_renderers_list(node.name, 'All')

    def _status_request(self, node):
        if node.pluginProps['serial_no'] == 'NA':   # Check if this is a NetLink device: if no serial number then false
            # Potentially send a status update command but these may only work over 2 way IR, not the MasterLink
            self.mlgw.send_beo4_cmd(
                int(node.address),
                int(CONST.CMDS_DEST.get("AUDIO SOURCE")),
                int(CONST.BEO4_CMDS.get("STATUS"))
            )

            indigo.server.log(node.name + " does not support status requests")
        else:   # If netlink, request a status update
            self.blgw.query(dev_type="AV renderer", device=node.name)

    # ########################################################################################
    # Define callback function for message return from B&O Gateway
    def cb(self, name, header, payload, message):
        # ########################################################################################
        # Message handler
        # Handle Beo4 Command Events
        try:
            if message['payload_type'] == "BEO4_KEY":
                self.beo4_key(message)
        except KeyError:
            pass

        # Handle Light and Command Events
        try:
            if message['Type'] == "LIGHT COMMAND":
                self.light_key(message)
            elif message['Type'] == "CONTROL COMMAND":
                self.control_key(message)
        except KeyError:
            pass

        # Handle Virtual Button Events
        try:
            if message['payload_type'] == "MLGW virtual button event":
                self.virtual_button(message)
        except KeyError:
            pass

        # Handle all standby events
        try:
            if message["command"] == "All Standby":
                for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
                    node.updateStatesOnServer(CONST.standby_state)
                    node.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

                indigo.devices['Bang and Olufsen Gateway'].updateStatesOnServer(CONST.gw_all_stb)
        except KeyError:
            pass

        # Handle AV Events
        try:
            # Use regular incoming messages to sync nowPlaying data
            if self.gateway.states['AudioRenderers'] != '' and \
                    self.gateway.states['currentAudioSource'] == str(self.itunes_source) and \
                    self.itunes_control:
                self._get_itunes_track_info(message)

            # For messages of type AV RENDERER, scan keys to update device states
            if message["Type"] in ["AV RENDERER", "RESPONSE"]:
                # Tidy up messages
                self.av_sanitise(message)
                # Filter messages that don't constitute meaningful state updates
                actionable = self.filter_messages(message)
                if self.debug:
                    indigo.server.log("Process message: " + str(actionable), level=logging.WARNING)
                if actionable:
                    # Keep track of what sources are playing on the network
                    self.src_tracking(message)
                    # Update individual devices based on updates
                    self.dev_update(message)
        except KeyError:
            pass

        # Report message content to log
        if self.verbose:
            if 'State_Update' in message and 'CONNECTION' in message['State_Update']:
                # Don't print pong responses from regular client ping to check sockets are open -
                # approx every 600 seconds
                pass
            elif 'Device' in message and message['Device'] == 'Clock':
                # Don't print the Clock sync telegrams from the HIP -
                # approx every 60 seconds
                pass
            elif 'payload_type' in message and message['payload_type'] == '0x14':
                # Don't print the Clock sync telegrams from the ML -
                # approx every 6 seconds
                pass
            elif 'payload_type' in message and message['payload_type'] == 'CLOCK' and not self.debug:
                # Don't print the Clock message telegrams from the ML
                pass
            else:
                self.message_log(name, header, payload, message)

        # Report Thread Count
        if self.debug:
            thread_count = int(threading.active_count())
            if thread_count > 1:
                indigo.server.log("Current Thread Count = " + str(thread_count), level=logging.DEBUG)

    # ########################################################################################
    # AV Handler Functions

    # #### Message Conditioning
    def av_sanitise(self, message):
        # Sanitise AV messages
        try:  # Check for missing source information
            if message['State_Update']['source'] in [None, 'None', '']:
                message['State_Update']['source'] = 'Unknown'
                message['State_Update']['sourceName'] = 'Unknown'

                # Update for standby condition
                message['State_Update']['state'] = "Standby"
        except KeyError:
            pass

        try:  # Check for unknown state
            if message['State_Update']['state'] in [None, 'None', '']:
                message['State_Update']['state'] = 'Unknown'
        except KeyError:
            pass

        try:  # Sanitise unknown Channel/Tracks
            if message['State_Update']['nowPlayingDetails']['channel_track'] in [0, 255, '0', '255']:
                del message['State_Update']['nowPlayingDetails']['channel_track']
        except KeyError:
            pass

        try:    # Add sourceName if not in message block
            if 'sourceName' not in message['State_Update']:
                # Find the sourceName from the source list for this device
                if 'Device' in message:     # If device known use local source data
                    self.find_source_name(message['State_Update']['source'],
                                          indigo.devices[message['Device']].pluginProps['sources'])
                else:   # If device not known use global source data
                    message['State_Update']['sourceName'] = \
                        dict(CONST.available_sources).get(message['State_Update']['source'])
        except KeyError:
            pass

        try:
            if message['State_Update']['source'] == str(self.itunes_source) and \
                    message['State_Update']['nowPlaying'] in [0, '0', '', 'Unknown']:
                # If the source is iTunes and current track unknown then set to currently playing track
                indigo.server.log('Telegram current track "unknown" - setting to iTunes currently playing',
                                  level=logging.DEBUG)
                message['State_Update']['nowPlaying'] = self.gateway.states['nowPlaying']

        except KeyError:
            pass

        try:    # Catch GOTO_SOURCE commands and set the goto_flag
            if message['payload_type'] == 'GOTO_SOURCE':
                self.goto_flag = datetime.now()
                if self.debug:
                    indigo.server.log("GOTO_SOURCE command received - goto_flag set", level=logging.WARNING)
        except KeyError:
            pass

    def filter_messages(self, message):
        # Filter state updates that are:
        # 1. Standby states that are received between source changes:
        # If device is changing source the state changes as follows [Old Source -> Standby -> New Source].
        # If the standby condition is processed, the New Source state will be filtered by the condition below
        #
        # 2. Play states that received <2 seconds after standby state set:
        # Some messages come in on the ML and HIP protocols relating to previous state etc.
        # These can be ignored to avoid false states for the indigo devices
        try:
            for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
                if node.name == message['Device']:

                    # Get time since last state update for this device
                    time_delta1 = datetime.now() - node.lastChanged
                    time_delta1 = time_delta1.total_seconds()
                    # Get time since last GOTO_SOURCE command
                    time_delta2 = datetime.now() - self.goto_flag
                    time_delta2 = time_delta2.total_seconds()

                    # If standby command received <2.0 seconds after GOTO_SOURCE command , ignore
                    if 'state' in message['State_Update'] and message['State_Update']['state'] == "Standby" \
                            and time_delta2 < 2.0:                                                  # Condition 1
                        if self.debug:
                            indigo.server.log(message['Device'] + " ignoring Standby: " + str(round(time_delta2, 2)) +
                                              " seconds elapsed since GOTO_STATE command - ignoring message!",
                                              level=logging.DEBUG)
                        return False

                    # If message received <2 seconds after standby state, ignore
                    elif node.states['playState'] == "Standby" and time_delta1 < 2.0:               # Condition 2
                        if self.debug:
                            indigo.server.log(message['Device'] + " in Standby: " + str(round(time_delta1, 2)) +
                                              " seconds elapsed since last state update - ignoring message!",
                                              level=logging.DEBUG)
                        return False
                    else:
                        return True
        except KeyError:
            return False

    # #### State tracking
    def src_tracking(self, message):
        # Track active renderers via gateway device
        try:
            # If new source is an audio source then update the gateway accordingly
            if message['State_Update']['source'] in CONST.source_type_dict.get('Audio Sources'):
                try:
                    # Keep track of which devices are playing audio sources
                    if message['Device'] not in self.gateway.states['AudioRenderers'] and \
                            message['State_Update']['state'] not in ['Standby', 'Unknown', 'None']:

                        # Log current audio source (MasterLink allows a single audio source for distribution)
                        source = message['State_Update']['source']
                        sourceName = dict(CONST.available_sources).get(source)

                        self.gateway.updateStateOnServer('currentAudioSource', value=source)
                        self.gateway.updateStateOnServer('currentAudioSourceName', value=sourceName)

                        try:
                            self.gateway.updateStateOnServer('nowPlaying', value=message['State_Update']['nowPlaying'])
                        except KeyError:
                            self.gateway.updateStateOnServer('nowPlaying', value='Unknown')

                        self.add_to_renderers_list(message['Device'], 'Audio')

                    # Remove device from Video Renderers list if it is on there
                    if message['Device'] in self.gateway.states['VideoRenderers']:
                        self.remove_from_renderers_list(message['Device'], 'Video')

                except KeyError:
                    pass

                # If source is N.Music then control accordingly
                if message['State_Update']['source'] == str(self.itunes_source) and self.itunes_control:
                    self.iTunes_transport_control(message)

            # If new source is an video source then update the gateway accordingly
            elif message['State_Update']['source'] in CONST.source_type_dict.get('Video Sources'):
                try:
                    # Keep track of which devices are playing video sources
                    if message['Device'] not in self.gateway.states['VideoRenderers'] and \
                            message['State_Update']['state'] not in ['Standby', 'Unknown', 'None']:
                        self.add_to_renderers_list(message['Device'], 'Video')

                    # Remove device from Audio Renderers list if it is on there
                    if message['Device'] in self.gateway.states['AudioRenderers']:
                        self.remove_from_renderers_list(message['Device'], 'Audio')

                except KeyError:
                    pass
        except KeyError:
            pass

    def dev_update(self, message):
        # Update device states
        try:
            for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
                if node.name == message['Device']:
                    # Handle Standby state
                    if message['State_Update']['state'] == "Standby":
                        # Update states to standby values
                        node.updateStatesOnServer(CONST.standby_state)
                        node.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

                        # Remove the device from active renderers list
                        self.remove_from_renderers_list(message['Device'], 'All')

                        # Post state update in Apple Notification Centre
                        if self.notifymode:
                            self.iTunes.notify(node.name + " now in Standby", "Device State Update")
                        return

                    # If device not in standby then update its state information
                    # get current states as list        # Index
                    last_state = [
                        node.states['playState'],       # 0
                        node.states['source'],          # 1
                        node.states['nowPlaying'],      # 2
                        node.states['channelTrack'],    # 3
                        node.states['volume'],          # 4
                        node.states['mute'],            # 5
                        node.states['onOffState']       # 6
                    ]

                    # Initialise new state list - the device is not in standby so it must be on
                    new_state = last_state[:]
                    new_state[6] = True

                    # Update device states with values from message
                    if 'state' in message['State_Update']:
                        if message['State_Update']['state'] not in ['None', 'Standby', '', None]:
                            if last_state[0] == 'Standby' and message['State_Update']['state'] == 'Unknown':
                                new_state[0] = 'Play'
                            elif last_state[0] != 'Standby' and message['State_Update']['state'] == 'Unknown':
                                pass
                            else:
                                new_state[0] = message['State_Update']['state']

                    if 'sourceName' in message['State_Update'] and message['State_Update']['sourceName'] != 'Unknown':
                        # Sanitise source name to avoid indigo key errors (remove whitespace)
                        source_name = message['State_Update']['sourceName'].strip().replace(" ", "_")
                        new_state[1] = source_name

                    if 'nowPlaying' in message['State_Update']:
                        # Update now playing information unless the state value is empty or unknown
                        if message['State_Update']['nowPlaying'] not in [0, '0', '', 'Unknown']:
                            new_state[2] = message['State_Update']['nowPlaying']
                        # If the state value is empty/unknown and the source has not changed then no update required
                        elif new_state[1] != last_state[1]:
                            # If the state has changed and the value is unknown, then set as "Unknown"
                            new_state[2] = 'Unknown'

                    if 'nowPlayingDetails' in message['State_Update'] and \
                            'channel_track' in message['State_Update']['nowPlayingDetails']:
                        new_state[3] = message['State_Update']['nowPlayingDetails']['channel_track']
                    elif new_state[1] != last_state[1]:
                        # If the state has changed and the value is unknown, then set as "Unknown"
                        new_state[2] = 0

                    if 'volume' in message['State_Update']:
                        new_state[4] = message['State_Update']['volume']

                    try:    # Check for mute state
                        if message['State_Update']['sound_status']['mute_status'] == 'Muted':
                            new_state[5] = True
                        else:
                            new_state[5] = False
                    except KeyError:
                        new_state[5] = False

                    if new_state != last_state:
                        # Update states on server
                        key_value_list = [
                            {'key': 'playState', 'value': new_state[0]},
                            {'key': 'source', 'value': new_state[1]},
                            {'key': 'nowPlaying', 'value': new_state[2]},
                            {'key': 'channelTrack', 'value': new_state[3]},
                            {'key': 'volume', 'value': new_state[4]},
                            {'key': 'mute', 'value': new_state[5]},
                            {'key': 'onOffState', 'value': new_state[6]},
                        ]
                        node.updateStatesOnServer(key_value_list)

                        # Post notifications Notifications
                        if self.notifymode:
                            self.notifications(node.name, last_state, new_state)

                        # Update state image on server
                        if new_state[0] == "Stopped":
                            node.updateStateImageOnServer(indigo.kStateImageSel.AvPaused)
                        elif new_state[0] not in ['None', 'Unknown', 'Standby', '', None]:
                            node.updateStateImageOnServer(indigo.kStateImageSel.AvPlaying)

                        # If audio source active, update any other active audio renderers accordingly
                        try:
                            if new_state[0] not in ['None', 'Unknown', 'Standby', '', None] and \
                                    message['State_Update']['source'] in CONST.source_type_dict.get('Audio Sources'):
                                self.all_audio_nodes_update(new_state, node.name, message['State_Update']['source'])
                        except KeyError:
                            pass

                        break
        except KeyError:
            pass

    def all_audio_nodes_update(self, new_state, dev, source):
        # Loop over all active audio renderers to update them with the latest audio state
        for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
            if node.name in self.gateway.states['AudioRenderers'] and node.name != dev:
                # Get current state of this node
                last_state = [
                    node.states['playState'],
                    node.states['source'],
                    node.states['nowPlaying'],
                    node.states['channelTrack'],
                    node.states['volume'],
                    node.states['mute'],
                ]

                if last_state[:4] != new_state[:4]:
                    # Update the play state for active Audio renderers if new values are different from current ones
                    key_value_list = [
                        {'key': 'onOffState', 'value': True},
                        {'key': 'playState', 'value': new_state[0]},
                        {'key': 'source', 'value': new_state[1]},
                        {'key': 'nowPlaying', 'value': new_state[2]},
                        {'key': 'channelTrack', 'value': new_state[3]},
                        {'key': 'mute', 'value': False},
                    ]
                    node.updateStatesOnServer(key_value_list)
                    node.updateStateImageOnServer(indigo.kStateImageSel.AvPlaying)

        # Update the gateway
        if self.gateway.states['currentAudioSourceName'] != new_state[1]:
            # If the source has changed, update both source and nowPlaying
            sourceName = new_state[1]

            key_value_list = [
                {'key': 'currentAudioSource', 'value': source},
                {'key': 'currentAudioSourceName', 'value': sourceName},
                {'key': 'nowPlaying', 'value': new_state[2]},
            ]
            self.gateway.updateStatesOnServer(key_value_list)

        elif self.gateway.states['nowPlaying'] != new_state[2] and new_state[2] not in ['', 'Unknown']:
            # If the source has not changed, and nowPlaying is not Unknown, update nowPlaying
            self.gateway.updateStateOnServer('nowPlaying', value=new_state[2])

    # #### Active renderer list maintenance
    def add_to_renderers_list(self, dev, av):
        if av == "Audio":
            renderer_list = 'AudioRenderers'
            renderer_count = 'nAudioRenderers'
        else:
            renderer_list = 'VideoRenderers'
            renderer_count = 'nVideoRenderers'

        # Retrieve the renderers and convert from string to list
        renderers = self.gateway.states[renderer_list].split(', ')

        # Sanitise the list for stray blanks
        if '' in renderers:
            renderers.remove('')

        # Add device to list if not already on there
        if dev not in renderers:
            renderers.append(dev)
            self.gateway.updateStateOnServer(renderer_list, value=', '.join(renderers))
            self.gateway.updateStateOnServer(renderer_count, value=len(renderers))

    def remove_from_renderers_list(self, dev, av):
        # Remove devices from renderers lists when the enter standby mode
        if av in ['Audio', 'All']:
            if dev in self.gateway.states['AudioRenderers']:
                renderers = self.gateway.states['AudioRenderers'].split(', ')
                renderers.remove(dev)

                self.gateway.updateStateOnServer('AudioRenderers', value=', '.join(renderers))
                self.gateway.updateStateOnServer('nAudioRenderers', value=len(renderers))

        if av in ['Video', 'All']:
            if dev in self.gateway.states['VideoRenderers']:
                renderers = self.gateway.states['VideoRenderers'].split(', ')
                renderers.remove(dev)

                self.gateway.updateStateOnServer('VideoRenderers', value=', '.join(renderers))
                self.gateway.updateStateOnServer('nVideoRenderers', value=len(renderers))

        # If no audio sources are playing then update the gateway states
        if self.gateway.states['AudioRenderers'] == '':
            key_value_list = [
                {'key': 'AudioRenderers', 'value': ''},
                {'key': 'nAudioRenderers', 'value': 0},
                {'key': 'currentAudioSource', 'value': 'Unknown'},
                {'key': 'currentAudioSourceName', 'value': 'Unknown'},
                {'key': 'nowPlaying', 'value': 'Unknown'},
            ]
            self.gateway.updateStatesOnServer(key_value_list)

            # If no AV renderers are playing N.Music, stop iTunes playback
            if self.itunes_control:
                self.iTunes.stop()

    # #### Helper functions
    @staticmethod
    def find_source_name(source, sources):
        # Get the sourceName for source
        for source_name in sources:
            if sources[source_name]['source'] == str(source):
                return str(sources[source_name]).split()[0]

        # if source list exhausted and no valid name found return Unknown
        return 'Unknown'

    @staticmethod
    # Get the source ID for sourceName
    def get_source(sourceName, sources):
        for source_name in sources:
            if source_name == sourceName:
                return str(sources[source_name]['source'])

        # if source list exhausted and no valid name found return Unknown
        return 'Unknown'

    # ########################################################################################
    # Apple Music Control and feedback
    def iTunes_transport_control(self, message):
        # Transport controls for iTunes
        try:  # If N.MUSIC command, trigger appropriate self.iTunes control
            if message['State_Update']['state'] not in ["", "Standby"]:
                self.iTunes.play(self.playlist_default)
        except KeyError:
            pass

        try:  # If N.MUSIC selected and Beo4 command received then run appropriate transport commands
            if message['State_Update']['command'] == "Go/Play":
                self.iTunes.play(self.playlist_default)

            elif message['State_Update']['command'] == "Stop":
                self.iTunes.pause()

            elif message['State_Update']['command'] == "Exit":
                self.iTunes.stop()

            elif message['State_Update']['command'] == "Step Up":
                self.iTunes.next_track()

            elif message['State_Update']['command'] == "Step Down":
                self.iTunes.previous_track()

            elif message['State_Update']['command'] == "Wind":
                self.iTunes.wind(15)

            elif message['State_Update']['command'] == "Rewind":
                self.iTunes.rewind(-15)

            elif message['State_Update']['command'] == "Shift-1/Random":
                self.iTunes.shuffle()

            elif "Digit-" in message['State_Update']['command']:
                rating = int(message['State_Update']['command'][-1:]) * 100/9
                self.iTunes.set_rating(int(rating))

            # If 'Info' pressed - update track info
            elif message['State_Update']['command'] == "Info":
                track_info = self.iTunes.get_current_track_info()
                if track_info[0] not in [None, 'None']:
                    indigo.server.log(
                        "\n\t----------------------------------------------------------------------------"
                        "\n\tiTUNES CURRENT TRACK INFO:"
                        "\n\t============================================================================"
                        "\n\tNow playing: '" + track_info[0] + "'"
                        "\n\t             by " + track_info[2] +
                        "\n\t             from the album '" + track_info[1] + "'"
                        "\n\t----------------------------------------------------------------------------"
                        "\n\tACTIVE AUDIO RENDERERS: " + str(self.gateway.states['AudioRenderers']) + "\n\n",
                        level=logging.DEBUG
                    )
                    s = 'say ' + track_info[0] + ', by ' + track_info[2] + ', from the album, ' + track_info[1]
                    os.system(s)

                self.iTunes.notify(
                    "Now playing: '" + track_info[0] +
                    "' by " + track_info[2] +
                    "from the album '" + track_info[1] + "'",
                    "Apple Music Track Info:"
                )

            # If 'Guide' pressed - print instructions to indigo log
            elif message['State_Update']['command'] == "Guide":
                indigo.server.log(
                    "\n\t----------------------------------------------------------------------------"
                    "\n\tBeo4/BeoRemote One Control of Apple Music"
                    "\n\tKey mapping guide: [Key : Action]"
                    "\n\t============================================================================"
                    "\n\n\t** BASIC TRANSPORT CONTROLS **"
                    "\n\tGO/PLAY        : Play"
                    "\n\tSTOP/Pause     : Pause"
                    "\n\tEXIT           : Stop"
                    "\n\tStep Up/P+     : Next Track"
                    "\n\tStep Down/P-   : Previous Track"
                    "\n\tWind           : Scan Forwards 15 Seconds"
                    "\n\tRewind         : Scan Backwards 15 Seconds"
                    "\n\n\t** DIGITS **"
                    "\n\tDigit  0       : Rate Track at 0 (0%), dislike it, and disable it from playback"
                    "\n\tDigits 1 to 8  : Rate Track from 1 (10%) to 8 (90%)"
                    "\n\tDigit  9       : Rate Track at 9 (100%) and 'love'' it"
                    "\n\n\t** FUNCTIONS **"
                    "\n\tShift-1/Random : Toggle Shuffle"
                    "\n\tINFO           : Display Track Info for Current Track"
                    "\n\tGUIDE          : This Guide"
                    "\n\n\t** ADVANCED CONTROLS **"
                    "\n\tGreen          : Shuffle Playlist '" + self.playlist_green + "'"
                    "\n\tYellow         : Shuffle Playlist '" + self.playlist_yellow + "'"
                    "\n\tRed            : Shuffle Playlist '" + self.playlist_red + "'"
                    "\n\tBlue           : Shuffle Playlist '" + self.playlist_blue + "'\n\n",
                    level=logging.DEBUG
                )

            # If colour key pressed, execute the appropriate applescript
            elif message['State_Update']['command'] == "Green":
                # Play a specific playlist - defaults to Recently Played
                # script = ASBridge.__file__[:-12] + '/Scripts/green.scpt'
                # self.iTunes.run_script(script, self.debug)
                if self.playlist_green != 'None':
                    self.iTunes.play_playlist(self.playlist_green)

            elif message['State_Update']['command'] == "Yellow":
                # Play a specific playlist - defaults to URL Radio stations
                # script = ASBridge.__file__[:-12] + '/Scripts/yellow.scpt'
                # self.iTunes.run_script(script, self.debug)
                if self.playlist_yellow != 'None':
                    self.iTunes.play_playlist(self.playlist_yellow)

            elif message['State_Update']['command'] == "Blue":
                # Play the current album
                # script = ASBridge.__file__[:-12] + '/Scripts/blue.scpt'
                # self.iTunes.run_script(script, self.debug)
                if self.playlist_blue != 'None':
                    self.iTunes.play_playlist(self.playlist_blue)

            # elif message['State_Update']['command'] in ["0xf2", "Red", "MOTS"]:
            elif message['State_Update']['command'] == "Red":
                # More of the same (start a playlist with just current track and let autoplay find similar tunes)
                # script = ASBridge.__file__[:-12] + '/Scripts/red.scpt'
                # self.iTunes.run_script(script, self.debug)
                if self.playlist_red != 'None':
                    self.iTunes.play_playlist(self.playlist_red)
        except KeyError:
            pass

    def _get_itunes_track_info(self, message):
        track_info = self.iTunes.get_current_track_info()
        if track_info[0] not in [None, 'None']:
            # Construct track info string
            track_info_ = "'" + track_info[0].decode('utf8') + "' by " + track_info[2].decode('utf8') + \
                          " from the album '" + track_info[1].decode('utf8') + "'"

            # Add now playing info to the message block
            if 'Type' in message and message['Type'] == "AV RENDERER" and 'source' in message['State_Update'] \
                    and message['State_Update']['source'] == str(self.itunes_source) and \
                    'nowPlaying' in message['State_Update']:
                message['State_Update']['nowPlaying'] = track_info_
                message['State_Update']['nowPlayingDetails']['channel_track'] = int(track_info[3])

            # Print track info to log if trackmode is set to true (via config UI)
            src = dict(CONST.available_sources).get(self.itunes_source)
            if self.gateway.states['currentAudioSource'] == str(self.itunes_source) and \
                    track_info_ != self.gateway.states['nowPlaying'] and self.trackmode:
                indigo.server.log("\n\t----------------------------------------------------------------------------"
                                  "\n\tiTUNES CURRENT TRACK INFO:"
                                  "\n\t============================================================================"
                                  "\n\tNow playing: '" + track_info[0].decode('utf8') + "'"
                                  "\n\t             by " + track_info[2].decode('utf8') +
                                  "\n\t             from the album '" + track_info[1].decode('utf8') + "'"
                                  "\n\t----------------------------------------------------------------------------"
                                  "\n\tACTIVE AUDIO RENDERERS: " + str(self.gateway.states['AudioRenderers']) + "\n\n")

                if self.notifymode:
                    # Post track information to Apple Notification Centre
                    self.iTunes.notify(track_info_ + " from source " + src, "Now Playing:")

            # Update nowPlaying on the gateway device
            if track_info_ != self.gateway.states['nowPlaying'] and \
                    self.gateway.states['currentAudioSource'] == str(self.itunes_source):
                self.gateway.updateStateOnServer('nowPlaying', value=track_info_)

                # Update info on active Audio Renderers
                for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
                    if node.name in self.gateway.states['AudioRenderers']:
                        key_value_list = [
                            {'key': 'onOffState', 'value': True},
                            {'key': 'playState', 'value': 'Play'},
                            {'key': 'source', 'value': src},
                            {'key': 'nowPlaying', 'value': track_info_},
                            {'key': 'channelTrack', 'value': int(track_info[3])},
                        ]
                        node.updateStatesOnServer(key_value_list)
                        node.updateStateImageOnServer(indigo.kStateImageSel.AvPlaying)

    # ########################################################################################
    # Message Reporting
    @staticmethod
    def message_log(name, header, payload, message):
        # Set reporting level for message logging
        try:        # CLOCK messages are filtered except in debug mode
            if message['payload_type'] == 'CLOCK':
                debug_level = logging.DEBUG
            else:   # Everything else is for INFO
                debug_level = logging.INFO
        except KeyError:
            debug_level = logging.INFO

        # Pretty formatting - convert to JSON format then remove braces
        message = json.dumps(message, indent=4)
        for r in (('"', ''), (',', ''), ('{', ''), ('}', '')):
            message = str(message).replace(*r)

        # Print message data
        if len(payload) + 9 < 73:
            indigo.server.log("\n\t----------------------------------------------------------------------------" +
                              "\n\t" + name + ": <--DATA-RECEIVED!-<< " +
                              datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                              "\n\t============================================================================" +
                              "\n\tHeader: " + header +
                              "\n\tPayload: " + payload +
                              "\n\t----------------------------------------------------------------------------" +
                              message, level=debug_level)
        elif 73 < len(payload) + 9 < 137:
            indigo.server.log("\n\t----------------------------------------------------------------------------" +
                              "\n\t" + name + ": <--DATA-RECEIVED!-<< " +
                              datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                              "\n\t============================================================================" +
                              "\n\tHeader: " + header +
                              "\n\tPayload: " + payload[:66] + "\n\t\t" + payload[66:137] +
                              "\n\t----------------------------------------------------------------------------" +
                              message, level=debug_level)
        else:
            indigo.server.log("\n\t----------------------------------------------------------------------------" +
                              "\n\t" + name + ": <--DATA-RECEIVED!-<< " +
                              datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                              "\n\t============================================================================" +
                              "\n\tHeader: " + header +
                              "\n\tPayload: " + payload[:66] + "\n\t\t" + payload[66:137] + "\n\t\t" + payload[137:] +
                              "\n\t----------------------------------------------------------------------------" +
                              message, level=debug_level)

    def notifications(self, name, last_state, new_state):
        # Post state information to the Apple Notification Centre
        # Information index:
        #   node.states['playState'],       # 0
        #   node.states['source'],          # 1
        #   node.states['nowPlaying'],      # 2
        #   node.states['channelTrack'],    # 3
        #   node.states['volume'],          # 4
        #   node.states['mute'],            # 5
        #   node.states['onOffState']       # 6

        # Don't post notification if nothing has changed
        if last_state == new_state:
            return

        # Source status information
        if last_state[0] != new_state[0] and new_state[0] == "Standby":  # Power off
            self.iTunes.notify(
                name + " now in Standby",
                "Device State Update"
            )
            return
        elif last_state[1] != new_state[1] and new_state[0] != "Standby":  # Source Update
            self.iTunes.notify(
                name + " now playing from source " + new_state[1],
                "Device State Update"
            )
            return
        elif last_state[0] != new_state[0] and new_state[0] == "Play":  # Power on
            self.iTunes.notify(
                name + " Active",
                "Device State Update"
            )
            return

        # Channel/Track information
        if new_state[2] not in [None, 'None', '', 0, '0', 'Unknown']:   # Now Playing Update
            self.iTunes.notify(
                new_state[2] + " from source " + new_state[1],
                name + " Now Playing:"
            )
        elif last_state[3] != new_state[3] and new_state[3] not in [0, 255, '0', '255']:  # Channel/Track Update
            self.iTunes.notify(
                name + " now playing channel/track " + new_state[3] + " from source " + new_state[1],
                "Device Channel/Track Information"
            )

    # ########################################################################################
    # Indigo Server Methods
    def configure_clients(self):
        # Get Parameters from UI
        # Plugin polling and reporting parameters
        self.pollinterval = 595  # ping sent out at 9:55, response evaluated at 10:00
        self.trackmode = self.pluginPrefs.get("trackMode")
        self.verbose = self.pluginPrefs.get("verboseMode")
        self.notifymode = self.pluginPrefs.get("notifyMode")
        self.debug = self.pluginPrefs.get("debugMode")
        self.triggers = []

        # Plugin audio source control parameters
        self.default_audio_source = self.pluginPrefs.get("defaultAudio")
        self.goto_flag = datetime(1982, 4, 1, 13, 30, 00, 342380)

        # Plugin Apple Music control parameters
        self.itunes_control = self.pluginPrefs.get("iTunesControl")
        self.playlist_default = self.pluginPrefs.get("playlist_default")
        self.playlist_green = self.pluginPrefs.get("playlist_green")
        self.playlist_yellow = self.pluginPrefs.get("playlist_yellow")
        self.playlist_red = self.pluginPrefs.get("playlist_red")
        self.playlist_blue = self.pluginPrefs.get("playlist_blue")
        self.itunes_source = self.pluginPrefs.get("iTunesSource")

        # Gateway network address and login parameters
        self.host = str(self.pluginPrefs.get('address'))
        self.port = [int(self.pluginPrefs.get('mlgw_port')),
                     int(self.pluginPrefs.get('hip_port')),
                     23]  # Telnet port - 23
        self.user = str(self.pluginPrefs.get('userID'))
        self.pwd = str(self.pluginPrefs.get('password'))

        ###

        # Download the config file from the gateway and initialise the devices
        config = MLCONFIG.MLConfig(self.host, self.user, self.pwd, self.debug)
        self.gateway = indigo.devices['Bang and Olufsen Gateway']

        # Create MLGW Protocol and ML_CLI Protocol clients (basic command listening)
        indigo.server.log('Creating MLGW Protocol Client...', level=logging.WARNING)
        self.mlgw = MLGW.MLGWClient(self.host, self.port[0], self.user, self.pwd, 'MLGW protocol', self.debug, self.cb)
        asyncore.loop(count=10, timeout=0.2)

        indigo.server.log('Creating ML Command Line Protocol Client...', level=logging.WARNING)
        self.mlcli = MLCLI.MLCLIClient(self.host, self.port[2], self.user, self.pwd,
                                       'ML command line interface', self.debug, self.cb)
        # Log onto the MLCLI client and ascertain the gateway model
        asyncore.loop(count=10, timeout=0.2)

        # Now MLGW and MasterLink Command Line Client are set up, retrieve MasterLink IDs of products
        config.get_masterlink_id(self.mlgw, self.mlcli)

        # If the gateway is a BLGW use the BLHIP protocol, else use the legacy MLHIP protocol
        if self.mlcli.isBLGW:
            indigo.server.log('Creating BLGW Home Integration Protocol Client...', level=logging.WARNING)
            self.blgw = BLHIP.BLHIPClient(self.host, self.port[1], self.user, self.pwd,
                                          'BLGW Home Integration Protocol', self.debug, self.cb)
            self.mltn = None
        else:
            indigo.server.log('Creating MLGW Home Integration Protocol Client...', level=logging.WARNING)
            self.mltn = MLtn.MLtnClient(self.host, self.port[2], self.user, self.pwd, 'ML telnet client',
                                        self.debug, self.cb)
            self.blgw = None

    # Connection polling
    def check_connection(self, client):
        last = round(time.time() - client.last_received_at, 2)
        # Reconnect if socket has disconnected, or if no response received to last ping
        if not client.is_connected or last > 60:
            indigo.server.log("\t" + client.name + ": Reconnecting!", level=logging.WARNING)
            client.handle_close()
            self.sleep(0.5)
            client.client_connect()

    # Indigo main program loop
    def runConcurrentThread(self):
        try:
            while True:
                # If not configured yet, stall the programme flow until the user fills out the config UI
                while not os.path.exists(self.path):
                    indigo.server.log("Plugin not yet configured: Retrying in 10 seconds...", level=logging.WARNING)
                    self.sleep(10.0)

                # If configuration file exists, set up clients accordingly
                if not self.configured:
                    self.configure_clients()
                    self.configured = True

                # Ping all connections every 10 minutes to prompt messages on the network
                asyncore.loop(count=self.pollinterval, timeout=1)
                if self.mlgw.is_connected:
                    self.mlgw.ping()
                if self.mlcli.is_connected:
                    self.mlcli.ping()
                if self.mlcli.isBLGW:
                    if self.blgw.is_connected:
                        self.blgw.ping()
                else:
                    if self.mltn.is_connected:
                        self.mltn.ping()

                # Check the connections approximately every 10 minutes to keep sockets open
                asyncore.loop(count=5, timeout=1)
                self.check_connection(self.mlgw)
                self.check_connection(self.mlcli)
                if self.mlcli.isBLGW:
                    self.check_connection(self.blgw)
                else:
                    self.check_connection(self.mltn)

                self.sleep(0.5)

        except self.StopThread:
            raise asyncore.ExitNow('Server is quitting!')

    # Tidy up on shutdown
    def shutdown(self):
        indigo.server.log("Shutdown plugin")
        del self.mlgw
        del self.mlcli
        if self.mlcli.isBLGW:
            del self.blgw
        else:
            del self.mltn
        del self.iTunes
        raise asyncore.ExitNow('Server is quitting!')
