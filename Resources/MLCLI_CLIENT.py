import asynchat
import logging
import socket
import time
import json
from collections import OrderedDict

import Resources.CONSTANTS as const

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

        #clear login process lines before processing telegrams
        if self._i <= self._header_lines:
            self._i += 1
        if self._i == self._header_lines - 1:
            self.log.info("\tAuthenticated! Gateway type is " + telegram[0:4] + "\n")
            if telegram[0:4] != "MLGW":
                self.isBLGW = True

        #Process telegrams and return json data in human readable format
        if self._i > self._header_lines:
            items = telegram.split()[1:]
            if len(items):
                telegram=bytearray()
                for item in items:
                    try:
                        telegram.append(int(item[:-1],base=16))
                    except:
                        #abort if invalid character found
                        break

            #Decode any telegram with a valid 9 byte header, excluding typy 0x14 (regular clock sync pings)
            if len(telegram) >= 9 and telegram[7] != 0x14:
                #Header: To_Device/From_Device/1/Type/To_Source/From_Source/0/Payload_Type/Length
                header = telegram[:9]
                payload = telegram[9:]
                message = self._decode(telegram)
                self._report(header, payload, message)

    def client_connect(self):
        self.log.info('Connecting to host at %s, port %i', self._host, self._port)
        self.set_terminator(b'\r\n')
        # Create the socket
        try:
            socket.setdefaulttimeout(3)
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
        except socket.error, e:
            self.log.info("\tError opening connection to %s:%i - %s" % (self._host, self._port, e))
            self.handle_close()
        except socket.timeout, e:
            self.log.info("\tSocket connection to %s:%i timed out- %s" % (self._host, self._port, e))
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

    def send_cmd(self,telegram):
        try:
            self.push(telegram + "\r\n")
        except socket.error, e:
            self.log.info("Error sending data: %s" % e)
            self.handle_close()
        except socket.timeout, e:
            self.log.info("\tSocket connection to %s:%i timed out- %s" % (self._host, self._port, e))
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
    def _hexbyte(self, byte):
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
        if result == None:
            result = self._hexbyte(s)
            self.log.debug("UNKNOWN (type=" + result + ")")
        return str(result)

    def _get_type(self, d, s):
        rev_dict = {value: key for key, value in d.items()}
        for i in range(len(list(rev_dict))):
            if s in list(rev_dict)[i]:
                return rev_dict.get(list(rev_dict)[i])

    # ########################################################################################
    # ##### Decode Masterlink Protocol packet to a serializable dict

    def _decode(self, telegram):
        # Decode header
        message = OrderedDict()
        if const.devices:
            for device in const.devices:
                if device['ML_ID'] == telegram[1]:
                    message["Zone"] = device["Zone"].upper()
                    message["Room"] = device["Room"].uppr()
                    message["Type"] = "AV RENDERER"
                    message["Device"] = device["Device"]
        message["from_device"] = self._dictsanitize(const._ml_device_dict, telegram[1])
        message["from_source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[5])
        message["to_device"] = self._dictsanitize(const._ml_device_dict, telegram[0])
        message["to_source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[4])
        message["type"] = self._dictsanitize(const._ml_telegram_type_dict, telegram[3])
        message["payload_type"] = self._dictsanitize(const._ml_command_type_dict, telegram[7])
        message["payload_len"] = telegram[8] + 1
        message["payload"] = OrderedDict()

        # source status info
        # TTFF__TYDSOS__PTLLPS SR____LS______SLSHTR__ACSTPI________________________TRTR______
        if message.get("payload_type") == "STATUS_INFO":
            message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[10])
            message["payload"]["sourceID"] = telegram[10]
            message["payload"]["source_type"] = telegram[22]
            message["payload"]["local_source"] = telegram[13]
            message["payload"]["source_medium"] = self._hexword(telegram[18], telegram[17])
            message["payload"]["channel_track"] = (
                telegram[19] if telegram[8] < 27 else (telegram[36] * 256 + telegram[37])
            )
            message["payload"]["picture_identifier"] = self._dictsanitize(const._ml_pictureformatdict, telegram[23])
            message["payload"]["state"] = self._dictsanitize(const._sourceactivitydict, telegram[21])

        # display source information
        if message.get("payload_type") == "DISPLAY_SOURCE":
            _s = ""
            for i in range(0, telegram[8] - 5):
                _s = _s + chr(telegram[i + 15])
            message["payload"]["display_source"] = _s.rstrip()

        # extended source information
        if message.get("payload_type") == "EXTENDED_SOURCE_INFORMATION":
            message["payload"]["info_type"] = telegram[10]
            _s = ""
            for i in range(0, telegram[8] - 14):
                _s = _s + chr(telegram[i + 24])
            message["payload"]["info_value"] = _s

        # beo4 command
        if message.get("payload_type") == "BEO4_KEY":
            message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[10])
            message["payload"]["sourceID"] = telegram[10]
            message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[10])
            message["payload"]["command"] = self._dictsanitize(const.beo4_commanddict, telegram[11])

        # audio track info long
        if message.get("payload_type") == "TRACK_INFO_LONG":
            message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[11])
            message["payload"]["sourceID"] = telegram[11]
            message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[11])
            message["payload"]["channel_track"] = telegram[12]
            message["payload"]["state"] = self._dictsanitize(const._sourceactivitydict, telegram[13])

        # video track info
        if message.get("payload_type") == "VIDEO_TRACK_INFO":
            message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[13])
            message["payload"]["sourceID"] = telegram[13]
            message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[13])
            message["payload"]["channel_track"] = telegram[11] * 256 + telegram[12]
            message["payload"]["state"] = self._dictsanitize(const._sourceactivitydict, telegram[14])

        # track change info
        if message.get("payload_type") == "TRACK_INFO":
            message["payload"]["subtype"] = self._dictsanitize(const._ml_trackinfo_subtype_dict, telegram[9])
            if message["payload"].get("subtype") == "Change Source":
                message["payload"]["prev_source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[11])
                message["payload"]["prev_sourceID"] = telegram[11]
                message["payload"]["prev_source_type"] = self._get_type(
                    const._ml_selectedsource_type_dict, telegram[11])
                if len(telegram) > 18:
                    message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[22])
                    message["payload"]["sourceID"] = telegram[22]
            if message["payload"].get("subtype") == "Current Source":
                message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[11])
                message["payload"]["sourceID"] = telegram[11]
                message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[11])
            else:
                message["payload"]["subtype"] = "Undefined: " + self._hexbyte(telegram[9])

        # goto source
        if message.get("payload_type") == "GOTO_SOURCE":
            message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[11])
            message["payload"]["sourceID"] = telegram[11]
            message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[11])
            message["payload"]["channel_track"] = telegram[12]

        # remote request
        if message.get("payload_type") == "MLGW_REMOTE_BEO4":
            message["payload"]["command"] = self._dictsanitize(const.beo4_commanddict, telegram[14])
            message["payload"]["destination"] = self._dictsanitize(const._destselectordict, telegram[11])

        # request_key
        if message.get("payload_type") == "LOCK_MANAGER_COMMAND":
            message["payload"]["subtype"] = self._dictsanitize(
                const._ml_command_type_request_key_subtype_dict, telegram[9])

        # request distributed audio source
        if message.get("payload_type") == "REQUEST_DISTRIBUTED_SOURCE":
            message["payload"]["subtype"] = self._dictsanitize(const._ml_activity_dict, telegram[9])
            if message["payload"].get('subtype') == "Source Active":
                message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[13])
                message["payload"]["sourceID"] = telegram[13]
                message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[13])

        # request local audio source
        if message.get("payload_type") == "REQUEST_LOCAL_SOURCE":
            message["payload"]["subtype"] = self._dictsanitize(const._ml_activity_dict, telegram[9])
            if message["payload"].get('subtype') == "Source Active":
                message["payload"]["source"] = self._dictsanitize(const._ml_selectedsourcedict, telegram[11])
                message["payload"]["sourceID"] = telegram[11]
                message["payload"]["source_type"] = self._get_type(const._ml_selectedsource_type_dict, telegram[11])

        return message