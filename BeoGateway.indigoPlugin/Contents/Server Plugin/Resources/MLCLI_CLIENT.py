import indigo
import asynchat
import socket
import time
import logging
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class MLCLIClient(asynchat.async_chat):
    """Client to monitor raw packet traffic on the Masterlink network via the undocumented command line interface
    of the Bang & Olufsen Gateway."""
    def __init__(self, host_address='blgw.local', port=23, user='admin', pwd='admin', name='ML_CLI',
                 debug=False, cb=None):
        asynchat.async_chat.__init__(self)

        self.debug = debug

        self._host = host_address
        self._port = int(port)
        self._user = user
        self._pwd = pwd
        self.name = name
        self.is_connected = False

        self._i = 0
        self._header_lines = 6
        self._received_data = ""
        self.last_sent = ''
        self.last_sent_at = time.time()
        self.last_received = ''
        self.last_received_at = time.time()
        self.last_message = {}

        self.isBLGW = False

        # Optional callback function
        if cb:
            self.messageCallBack = cb
        else:
            self.messageCallBack = None

        # ########################################################################################
        # ##### Open Socket and connect to B&O Gateway
        self.client_connect()

    # ########################################################################################
    # ##### Client functions
    def collect_incoming_data(self, data):
        self._received_data += data

    def found_terminator(self):
        self.last_received = self._received_data
        self.last_received_at = time.time()
        
        telegram = self._received_data
        self._received_data = ""

        # Clear login process lines before processing telegrams
        if self._i <= self._header_lines:
            self._i += 1
        if self._i == self._header_lines - 1:
            indigo.server.log("\tAuthenticated! Gateway type is " + telegram[0:4] + "\n", level=logging.DEBUG)
            if telegram[0:4] != "MLGW":
                self.isBLGW = True

        # Process telegrams and return json data in human readable format
        if self._i > self._header_lines:
            if "---- Logging" in telegram:
                # Pong telegram
                header = telegram
                payload = []
                message = OrderedDict([('payload_type', 'Pong'), ('State_Update', dict([('CONNECTION', 'Online')]))])
                self.is_connected = True
                if self.messageCallBack:
                    self.messageCallBack(self.name, header, str(list(payload)), message)
            else:
                # ML protocol message detected
                items = telegram.split()[1:]
                if len(items):
                    telegram = bytearray()
                    for item in items:
                        try:
                            telegram.append(int(item[:-1], base=16))
                        except (ValueError, TypeError):
                            # abort if invalid character found
                            if self.debug:
                                indigo.server.log('Invalid character ' + str(item) + ' found in telegram: ' +
                                                  ''.join(items) + '\nAborting!', level=logging.ERROR)
                            break

                # Decode any telegram with a valid 9 byte header, excluding typy 0x14 (regular clock sync pings)
                if len(telegram) >= 9:
                    # Header: To_Device/From_Device/1/Type/To_Source/From_Source/0/Payload_Type/Length
                    header = telegram[:9]
                    payload = telegram[9:]
                    message = self._decode(telegram)
                    self._report(header, payload, message)

    def client_connect(self):
        indigo.server.log('Connecting to host at ' + self._host + ', port ' + str(self._port), level=logging.WARNING)
        self.set_terminator(b'\r\n')
        # Create the socket
        try:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as e:
            indigo.server.log("Error creating socket: " + str(e), level=logging.ERROR)
            self.handle_close()
        # Now connect
        try:
            self.connect((self._host, self._port))
        except socket.gaierror as e:
            indigo.server.log("\tError with address: " + str(e), level=logging.ERROR)
            self.handle_close()
        except socket.timeout as e:
            indigo.server.log("\tSocket connection timed out: " + str(e), level=logging.ERROR)
            self.handle_close()
        except socket.error as e:
            indigo.server.log("\tError opening connection: " + str(e), level=logging.ERROR)
            self.handle_close()
        else:
            self.is_connected = True
            indigo.server.log("\tConnected to B&O Gateway", level=logging.DEBUG)

    def handle_connect(self):
        indigo.server.log("\tAttempting to Authenticate...", level=logging.WARNING)
        self.send_cmd(self._pwd)
        self.send_cmd("_MLLOG ONLINE")

    def handle_close(self):
        indigo.server.log(self.name + ": Closing socket", level=logging.ERROR)
        self.is_connected = False
        self.close()

    def send_cmd(self, telegram):
        try:
            self.push(telegram + "\r\n")
        except socket.timeout as e:
            indigo.server.log("\tSocket connection timed out: " + str(e), level=logging.ERROR)
            self.handle_close()
        except socket.error as e:
            indigo.server.log("Error sending data: " + str(e), level=logging.ERROR)
            self.handle_close()
        else:
            self.last_sent = telegram
            self.last_sent_at = time.time()
            indigo.server.log(self.name + " >>-SENT--> : " + telegram, level=logging.INFO)
            time.sleep(0.2)

    def _report(self, header, payload, message):
        self.last_message = message
        if self.messageCallBack:
            self.messageCallBack(self.name, str(list(header)), str(list(payload)), message)

    def ping(self):
        if self.debug:
            indigo.server.log(self.name + " >>-SENT--> : Ping", level=logging.DEBUG)
        self.push('\n')

    # ########################################################################################
    # ##### Utility functions
    @staticmethod
    def _hexbyte(byte):
        resultstr = hex(byte)
        if byte < 16:
            resultstr = resultstr[:2] + "0" + resultstr[2]
        return resultstr

    def _hexword(self, byte1, byte2):
        resultstr = self._hexbyte(byte2)
        resultstr = self._hexbyte(byte1) + resultstr[2:]
        return resultstr

    def _dictsanitize(self, d, s):
        result = d.get(s)
        if result is None:
            result = self._hexbyte(s)
        return str(result)

    # ########################################################################################
    # ##### Decode Masterlink Protocol packet to a serializable dict
    def _decode(self, telegram):
        # Decode header
        message = OrderedDict()
        self._get_device_info(message, telegram)
        if 'Device' not in message:
            # If ML telegram has been matched to a Masterlink node in the devices list then the 'from_device'
            # key is redundant - it will always be identical to the 'Device' key
            message["from_device"] = self._dictsanitize(CONST.ml_device_dict, telegram[1])
        message["from_source"] = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[5])
        message["to_device"] = self._get_device_name(self._dictsanitize(CONST.ml_device_dict, telegram[0]))
        message["to_source"] = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[4])
        message["type"] = self._dictsanitize(CONST.ml_telegram_type_dict, telegram[3])
        message["payload_type"] = self._dictsanitize(CONST.ml_command_type_dict, telegram[7])
        message["payload_len"] = telegram[8] + 1
        message["State_Update"] = OrderedDict()

        # RELEASE command signifies product standby
        if message.get("payload_type") in ["RELEASE", "STANDBY"]:
            message["State_Update"]["state"] = 'Standby'

        # source status info
        # TTFF__TYDSOS__PTLLPS SR____LS______SLSHTR__ACSTPI________________________TRTR______
        if message.get("payload_type") == "STATUS_INFO":
            message["State_Update"]["nowPlaying"] = 'Unknown'

            if telegram[8] < 27:
                c_trk = telegram[19]
            else:
                c_trk = telegram[36] * 256 + telegram[37]

            message["State_Update"]["nowPlayingDetails"] = OrderedDict(
                [
                    ("local_source", telegram[13]),
                    ("type", self._dictsanitize(CONST.ml_sourcekind_dict, telegram[22])),
                    ("channel_track", c_trk),
                    ("source_medium_position", self._hexword(telegram[18], telegram[17])),
                    ("picture_format", self._dictsanitize(CONST.ml_pictureformatdict, telegram[23]))
                ]
            )
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[10])
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[10]
            self._get_channel_track(message)
            message["State_Update"]["state"] = self._dictsanitize(CONST.sourceactivitydict, telegram[21])

        # display source information
        if message.get("payload_type") == "DISPLAY_SOURCE":
            _s = ""
            for i in range(0, telegram[8] - 5):
                _s = _s + chr(telegram[i + 15])
            message["State_Update"]["display_source"] = _s.rstrip()

        # extended source information
        if message.get("payload_type") == "EXTENDED_SOURCE_INFORMATION":
            message["State_Update"]["info_type"] = telegram[10]
            _s = ""
            for i in range(0, telegram[8] - 14):
                _s = _s + chr(telegram[i + 24])
            message["State_Update"]["info_value"] = _s

        # beo4 command
        if message.get("payload_type") == "BEO4_KEY":
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[10])
            self._get_source_name(source, message)
            message["State_Update"] = OrderedDict(
                [
                    ("source", source),
                    ("sourceID", telegram[10]),
                    ("source_type", self._get_source_type(source)),
                    ("command", self._dictsanitize(CONST.beo4_commanddict, telegram[11]))
                ]
            )

        # audio track info long
        if message.get("payload_type") == "TRACK_INFO_LONG":
            message["State_Update"]["nowPlaying"] = 'Unknown'
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
            message["State_Update"]["nowPlayingDetails"] = OrderedDict(
                [
                    ("type", self._get_source_type(source)),
                    ("channel_track", telegram[12]),
                ]
            )
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[11]
            self._get_channel_track(message)
            message["State_Update"]["state"] = self._dictsanitize(CONST.sourceactivitydict, telegram[13])

        # video track info
        if message.get("payload_type") == "VIDEO_TRACK_INFO":
            message["State_Update"]["nowPlaying"] = 'Unknown'
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[13])
            message["State_Update"]["nowPlayingDetails"] = OrderedDict(
                [
                    ("source_type", self._get_source_type(source)),
                    ("channel_track", telegram[11] * 256 + telegram[12])
                ]
            )
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[13]
            self._get_channel_track(message)
            message["State_Update"]["state"] = self._dictsanitize(CONST.sourceactivitydict, telegram[14])

        # track change info
        if message.get("payload_type") == "TRACK_INFO":
            message["State_Update"]["subtype"] = self._dictsanitize(CONST.ml_trackinfo_subtype_dict, telegram[9])

            # Change source
            if message["State_Update"].get("subtype") == "Change Source":
                prev_source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
                message["State_Update"]["prev_source"] = prev_source
                message["State_Update"]["prev_sourceID"] = telegram[11]
                message["State_Update"]["prev_source_type"] = self._get_source_type(prev_source)
                if len(telegram) > 18:
                    source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[22])
                    self._get_source_name(source, message)
                    message["State_Update"]["source"] = source
                    message["State_Update"]["sourceID"] = telegram[22]

            # Current Source
            if message["State_Update"].get("subtype") == "Current Source":
                source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
                self._get_source_name(source, message)
                message["State_Update"]["source"] = source
                message["State_Update"]["sourceID"] = telegram[11]
                message["State_Update"]["source_type"] = self._get_source_type(source)
                message["State_Update"]["state"] = 'Unknown'
            else:
                message["State_Update"]["subtype"] = "Undefined: " + self._hexbyte(telegram[9])

        # goto source
        if message.get("payload_type") == "GOTO_SOURCE":
            message["State_Update"]["nowPlaying"] = 'Unknown'
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
            message["State_Update"]["nowPlayingDetails"] = OrderedDict(
                [
                    ("source_type", self._get_source_type(source)),
                    ("channel_track", telegram[12])
                ]
            )
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[11]
            if telegram[12] not in [0, 255]:
                self._get_channel_track(message)
            # Device sending goto source command is playing
            message["State_Update"]["state"] = 'Play'

        # remote request
        if message.get("payload_type") == "MLGW_REMOTE_BEO4":
            message["State_Update"]["command"] = self._dictsanitize(CONST.beo4_commanddict, telegram[14])
            message["State_Update"]["destination"] = self._dictsanitize(CONST.destselectordict, telegram[11])

        # request_key
        if message.get("payload_type") == "LOCK_MANAGER_COMMAND":
            message["State_Update"]["subtype"] = self._dictsanitize(
                CONST.ml_command_type_request_key_subtype_dict, telegram[9])

        # request distributed audio source
        if message.get("payload_type") == "REQUEST_DISTRIBUTED_SOURCE":
            message["State_Update"]["subtype"] = self._dictsanitize(CONST.ml_activity_dict, telegram[9])
            if message["State_Update"].get('subtype') == "Source Active":
                source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[13])
                self._get_source_name(source, message)
                message["State_Update"]["source"] = source
                message["State_Update"]["sourceID"] = telegram[13]
                message["State_Update"]["source_type"] = self._get_source_type(source)

        # request local audio source
        if message.get("payload_type") == "REQUEST_LOCAL_SOURCE":
            message["State_Update"]["subtype"] = self._dictsanitize(CONST.ml_activity_dict, telegram[9])
            if message["State_Update"].get('subtype') == "Source Active":
                source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
                self._get_source_name(source, message)
                message["State_Update"]["source"] = source
                message["State_Update"]["sourceID"] = telegram[11]
                message["State_Update"]["source_type"] = self._get_source_type(source)

        # request local audio source
        if message.get("payload_type") == "PICTURE_AND_SOUND_STATUS":
            message["State_Update"]["sound_status"] = OrderedDict(
                [
                    ("mute_status", self._dictsanitize(CONST.mlgw_soundstatusdict, telegram[10])),
                    ("speaker_mode", self._dictsanitize(CONST.mlgw_speakermodedict, telegram[11])),
                    # ("stereo_mode", self._dictsanitize(CONST.mlgw_stereoindicatordict, telegram[9]))
                ]
            )
            # message["State_Update"]["picture_status"] = OrderedDict()

            message['State_Update']['source'] = 'Unknown'
            message['State_Update']['sourceName'] = 'Unknown'
            message["State_Update"]["state"] = 'Unknown'
            message["State_Update"]["volume"] = int(telegram[12])

        return message

    @staticmethod
    def _get_device_info(message, telegram):
        # Loop over the device list
        for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
            # Get properties
            node_props = node.pluginProps

            # Skip netlink devices with no ml_id
            if node_props['mlid'] == 'NA':
                continue

            # identify if the mlid is a number or a text string
            try:
                ml_id = int(node_props['mlid'], base=16)
            except ValueError:
                # If it is a text mlid then loop over the dictionary and get the numeric key
                for item in CONST.ml_device_dict.items():
                    if item[1] == node_props['mlid']:
                        ml_id = int(item[0])

            if ml_id == int(telegram[1]):  # Match ML_ID
                try:
                    message["Zone"] = node_props['zone'].upper()
                except KeyError:
                    pass
                message["Room"] = node_props['room'].upper()
                message["Type"] = "AV RENDERER"
                message["Device"] = node.name
                break

    def _get_channel_track(self, message):
        try:
            node = indigo.devices[message['Device']]
            # Get properties
            node_props = node.pluginProps
            source_name = message["State_Update"]["sourceName"].strip().replace(" ", "_")
            if self.debug:
                indigo.server.log('searching device ' + node.name + ' channel list for source ' + source_name,
                                  level=logging.DEBUG)
            if 'channels' in node_props['sources'][source_name]:
                for channel in node_props['sources'][source_name]['channels']:
                    if self.debug:
                        indigo.server.log(source_name + " Channel " + channel[0][1:] + " = " + channel[1],
                                          level=logging.DEBUG)
                    if int(channel[0][1:]) == int(
                            message["State_Update"]['nowPlayingDetails']["channel_track"]):
                        message["State_Update"]["nowPlaying"] = channel[1]
                        if self.debug:
                            indigo.server.log("Current Channel: " + channel[1], level=logging.DEBUG)
                        return

            # If source list exhausted then return Unknown
            message["State_Update"]["nowPlaying"] = 'Unknown'
        except KeyError:
            message["State_Update"]["nowPlaying"] = 'Unknown'

    @staticmethod
    def _get_device_name(dev):
        for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
            # Get properties
            node_props = node.pluginProps
            if node_props['mlid'] == dev:
                return node.name
        return dev

    @staticmethod
    def _get_source_name(source, message):
        if CONST.available_sources:
            for src in CONST.available_sources:
                if str(src[0]) == str(source):
                    message["State_Update"]["sourceName"] = src[1]
                    return
        # If source list exhausted then return Unknown
        message["State_Update"]["sourceName"] = 'Unknown'

    @staticmethod
    def _get_source_type(source):
        if source in CONST.source_type_dict.get('Audio Sources'):
            return "AUDIO"
        elif source in CONST.source_type_dict.get('Video Sources'):
            return "VIDEO"
        else:
            return "OTHER"
