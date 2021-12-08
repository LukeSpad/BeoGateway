import asynchat
import logging
import socket
import time
import json
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class MLCLIClient(asynchat.async_chat):
    """Client to monitor raw packet traffic on the Masterlink network via the undocumented command line interface
    of the Bang & Olufsen Gateway."""
    def __init__(self, host_address='blgw.local', port=23, user='admin', pwd='admin', name='ML_CLI', cb=None):
        asynchat.async_chat.__init__(self)
        self.log = logging.getLogger('Client (%7s)' % name)
        self.log.setLevel('INFO')

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
        self.log.debug(data)
        self._received_data += data

    def found_terminator(self):
        self.last_received = self._received_data
        self.last_received_at = time.time()
        self.log.debug(self._received_data)
        
        telegram = self._received_data
        self._received_data = ""

        # Clear login process lines before processing telegrams
        if self._i <= self._header_lines:
            self._i += 1
        if self._i == self._header_lines - 1:
            self.log.info("\tAuthenticated! Gateway type is " + telegram[0:4] + "\n")
            if telegram[0:4] != "MLGW":
                self.isBLGW = True

        # Process telegrams and return json data in human readable format
        if self._i > self._header_lines:
            if "---- Logging" in telegram:
                # Pong telegram
                header = telegram
                payload = []
                message = OrderedDict([('payload_type', 'Pong'), ('CONNECTION', 'Online')])
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
                            self.log.debug('Invalid character ' + str(item) + ' found in telegram: ' +
                                           ''.join(items) + '\nAborting!')
                            break

                # Decode any telegram with a valid 9 byte header, excluding typy 0x14 (regular clock sync pings)
                if len(telegram) >= 9 and telegram[7] != 0x14:
                    # Header: To_Device/From_Device/1/Type/To_Source/From_Source/0/Payload_Type/Length
                    header = telegram[:9]
                    payload = telegram[9:]
                    message = self._decode(telegram)
                    self._report(header, payload, message)

    def client_connect(self):
        self.log.info('Connecting to host at %s, port %i', self._host, self._port)
        self.set_terminator(b'\r\n')
        # Create the socket
        try:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, e:
            self.log.info("Error creating socket: %s" % e)
            self.handle_close()
        # Now connect
        try:
            self.connect((self._host, self._port))
        except socket.gaierror, e:
            self.log.info("\tError with address %s:%i - %s" % (self._host, self._port, e))
            self.handle_close()
        except socket.timeout, e:
            self.log.info("\tSocket connection to %s:%i timed out- %s" % (self._host, self._port, e))
            self.handle_close()
        except socket.error, e:
            self.log.info("\tError opening connection to %s:%i - %s" % (self._host, self._port, e))
            self.handle_close()
        else:
            self.is_connected = True
            self.log.info("\tConnected to B&O Gateway")

    def handle_connect(self):
        self.log.info("\tAttempting to Authenticate...")
        self.send_cmd(self._pwd)
        self.send_cmd("_MLLOG ONLINE")

    def handle_close(self):
        self.log.info(self.name + ": Closing socket")
        self.is_connected = False
        self.close()

    def send_cmd(self, telegram):
        try:
            self.push(telegram + "\r\n")
        except socket.timeout, e:
            self.log.info("\tSocket connection to %s:%i timed out- %s" % (self._host, self._port, e))
            self.handle_close()
        except socket.error, e:
            self.log.info("Error sending data: %s" % e)
            self.handle_close()
        else:
            self.last_sent = telegram
            self.last_sent_at = time.time()
            self.log.info(self.name + " >>-SENT--> : " + telegram)
            time.sleep(0.2)

    def _report(self, header, payload, message):
        # Report messages, excluding regular clock pings from gateway
        self.last_message = message
        self.log.debug(self.name + "\n" + str(json.dumps(message, indent=4)))
        if self.messageCallBack:
            self.messageCallBack(self.name, str(list(header)), str(list(payload)), message)

    def ping(self):
        self.log.info(self.name + " >>-SENT--> : Ping")
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
            self.log.debug("UNKNOWN (type=" + result + ")")
        return str(result)

    @staticmethod
    def _get_type(d, s):
        rev_dict = {value: key for key, value in d.items()}
        for i in range(len(list(rev_dict))):
            if s in list(rev_dict)[i]:
                return rev_dict.get(list(rev_dict)[i])

    # ########################################################################################
    # ##### Decode Masterlink Protocol packet to a serializable dict
    def _decode(self, telegram):
        # Decode header
        message = OrderedDict()
        self._get_device_info(message, telegram)
        message["from_device"] = self._get_device_name(self._dictsanitize(CONST.ml_device_dict, telegram[1]))
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
            message["State_Update"]["nowPlayingDetails"] = OrderedDict()
            message["State_Update"]["nowPlayingDetails"]["local_source"] = telegram[13]
            message["State_Update"]["nowPlayingDetails"]["type"] = \
                self._dictsanitize(CONST.ml_sourcekind_dict, telegram[22])
            if telegram[8] < 27:
                message["State_Update"]["nowPlayingDetails"]["channel_track"] = telegram[19]
            else:
                message["State_Update"]["nowPlayingDetails"]["channel_track"] = telegram[36] * 256 + telegram[37]
            message["State_Update"]["nowPlayingDetails"]["source_medium_position"] = \
                self._hexword(telegram[18], telegram[17])
            message["State_Update"]["nowPlayingDetails"]["picture_format"] = \
                self._dictsanitize(CONST.ml_pictureformatdict, telegram[23])
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[10])
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[10]
            self._get_channel_track(telegram, message)
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
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[10]
            message["State_Update"]["source_type"] = self._get_type(CONST.ml_selectedsource_type_dict, telegram[10])
            message["State_Update"]["command"] = self._dictsanitize(CONST.beo4_commanddict, telegram[11])

        # audio track info long
        if message.get("payload_type") == "TRACK_INFO_LONG":
            message["State_Update"]["nowPlaying"] = 'Unknown'
            message["State_Update"]["nowPlayingDetails"] = OrderedDict()
            message["State_Update"]["nowPlayingDetails"]["type"] = \
                self._get_type(CONST.ml_selectedsource_type_dict, telegram[11])
            message["State_Update"]["nowPlayingDetails"]["channel_track"] = telegram[12]
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[11]
            self._get_channel_track(telegram, message)
            message["State_Update"]["state"] = self._dictsanitize(CONST.sourceactivitydict, telegram[13])

        # video track info
        if message.get("payload_type") == "VIDEO_TRACK_INFO":
            message["State_Update"]["nowPlaying"] = 'Unknown'
            message["State_Update"]["nowPlayingDetails"] = OrderedDict()
            message["State_Update"]["nowPlayingDetails"]["source_type"] = \
                self._get_type(CONST.ml_selectedsource_type_dict, telegram[13])
            message["State_Update"]["nowPlayingDetails"]["channel_track"] = telegram[11] * 256 + telegram[12]
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[13])
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[13]
            self._get_channel_track(telegram, message)
            message["State_Update"]["state"] = self._dictsanitize(CONST.sourceactivitydict, telegram[14])

        # track change info
        if message.get("payload_type") == "TRACK_INFO":
            message["State_Update"]["subtype"] = self._dictsanitize(CONST.ml_trackinfo_subtype_dict, telegram[9])

            # Change source
            if message["State_Update"].get("subtype") == "Change Source":
                message["State_Update"]["prev_source"] = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
                message["State_Update"]["prev_sourceID"] = telegram[11]
                message["State_Update"]["prev_source_type"] = self._get_type(
                    CONST.ml_selectedsource_type_dict, telegram[11])
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
                message["State_Update"]["source_type"] = self._get_type(CONST.ml_selectedsource_type_dict, telegram[11])
            else:
                message["State_Update"]["subtype"] = "Undefined: " + self._hexbyte(telegram[9])

        # goto source
        if message.get("payload_type") == "GOTO_SOURCE":
            message["State_Update"]["nowPlaying"] = 'Unknown'
            message["State_Update"]["nowPlayingDetails"] = OrderedDict()
            message["State_Update"]["nowPlayingDetails"]["source_type"] = \
                self._get_type(CONST.ml_selectedsource_type_dict, telegram[11])
            message["State_Update"]["nowPlayingDetails"]["channel_track"] = telegram[12]
            source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
            self._get_source_name(source, message)
            message["State_Update"]["source"] = source
            message["State_Update"]["sourceID"] = telegram[11]
            self._get_channel_track(telegram, message)

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
                message["State_Update"]["source_type"] = self._get_type(CONST.ml_selectedsource_type_dict, telegram[13])

        # request local audio source
        if message.get("payload_type") == "REQUEST_LOCAL_SOURCE":
            message["State_Update"]["subtype"] = self._dictsanitize(CONST.ml_activity_dict, telegram[9])
            if message["State_Update"].get('subtype') == "Source Active":
                source = self._dictsanitize(CONST.ml_selectedsourcedict, telegram[11])
                self._get_source_name(source, message)
                message["State_Update"]["source"] = source
                message["State_Update"]["sourceID"] = telegram[11]
                message["State_Update"]["source_type"] = self._get_type(CONST.ml_selectedsource_type_dict, telegram[11])

        return message

    @staticmethod
    def _get_channel_track(telegram, message):
        # Check device list for channel name information
        if CONST.devices:
            for device in CONST.devices:
                # Loop over devices to find source list for this specific device
                if device['ML_ID'] == telegram[1]:
                    if 'channels' in device['Sources'][message["State_Update"]["source"]]:
                        for channel in device['Sources'][message["State_Update"]["source"]]['channels']:
                            if channel['number'] == message["State_Update"]["nowPlayingDetails"]["channel_track"]:
                                message["State_Update"]["nowPlaying"] = channel['name']
                                return
            # If device is a NetLink device and has no ML_ID, seek a generic solution from the first device that has
            # this source available: This could give an incorrect response if a link room device has a different
            # favorites list to the Audio Master!
            for device in CONST.devices:
                if message["State_Update"]["source"] in device['Sources']:
                    if 'channels' in device['Sources'][message["State_Update"]["source"]]:
                        for channel in device['Sources'][message["State_Update"]["source"]]['channels']:
                            if channel['number'] == message["State_Update"]["nowPlayingDetails"]["channel_track"]:
                                message["State_Update"]["nowPlaying"] = channel['name']
                                return

    def _get_device_info(self, message, telegram):
        if CONST.devices:
            for device in CONST.devices:
                if device['ML_ID'] == self._dictsanitize(CONST.ml_device_dict, telegram[1]):
                    try:
                        message["Zone"] = device['Zone'].upper()
                    except KeyError:
                        pass
                    message["Room"] = device["Room"].upper()
                    message["Type"] = "AV RENDERER"
                    message["Device"] = device["Device"]
                    break

    @staticmethod
    def _get_device_name(dev):
        if CONST.devices:
            for device in CONST.devices:
                if device['ML_ID'] == dev:
                    return device['Device']
            return dev

    @staticmethod
    def _get_source_name(source, message):
        if CONST.available_sources:
            for src in CONST.available_sources:
                if src[1] == source:
                    message["State_Update"]["sourceName"] = src[0]
                    break
