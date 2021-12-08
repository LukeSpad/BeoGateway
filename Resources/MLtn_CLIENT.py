import asynchat
import logging
import socket
import time
import json
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class MLtnClient(asynchat.async_chat):
    """Client to monitor network activity on a Masterlink Gateway via the telnet monitor"""
    def __init__(self, host_address='mlgw.local', port=23, user='admin', pwd='admin', name='MLGW_HIP', cb=None):
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
        self._header_lines = 4
        self._received_data = ''
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

        items = self._received_data.split(' ')

        if self._i <= self._header_lines:
            self._i += 1
            if self._received_data[0:4] != "MLGW":
                self.isBLGW = True
            if self._i == self._header_lines - 1:
                self.log.info("\t" + self._received_data)
                if self._received_data == 'incorrect password':
                    self.handle_close()

        else:
            try:
                self._decode(items)
            except IndexError:
                self.log.debug(str(list(items)))

        self._received_data = ""

    def _decode(self, items):
        header = items[3][:-1]
        telegram_starts = len(''.join(items[:4])) + 4
        telegram = self._received_data[telegram_starts:].replace('!', '').split('/')
        message = OrderedDict()

        if telegram[0] == 'Monitor events ( keys: M, E, C, (spc), Q ) ----':
            self.toggle_commands()
            self.toggle_macros()

        if header == 'integration_protocol':
            message = self._decode_ip(telegram, message)

        if header == 'resource_found':
            message['State_Update'] = telegram[0]

        if header == 'action_executed':
            message = self._decode_action(telegram, message)

        if header == 'command_executed':
            message = self._decode_command(telegram, message)

        if header == 'macro_fired':
            message['Zone'] = telegram[0].upper()
            message['Room'] = telegram[1].upper()
            message['Macro_Name'] = telegram[3]

        if header == 'trigger_fired':
            message = self._decode_trigger(telegram, message)

        self._report(header, telegram, message)

    def _decode_ip(self, telegram, message):
        if ''.join(telegram).split(':')[0] == 'Integration Protocol login':
            chars = ''.join(telegram).split(':')[1][2:].split(' ')
            message['Payload'] = ''
            for c in chars:
                if c == '0x0':
                    message['Payload'] += '0'
                else:
                    message['Payload'] += chr(int(c, base=16))

        if ''.join(telegram).split(':')[0] == 'Integration Protocol':
            if ''.join(telegram).split(':')[1] == ' processed serial number request':
                message['Payload'] = 'processed serial number request'
            else:
                s = ''.join(telegram).split(' ')
                message['Type'] = 'Send Beo4 Command'
                message[s[5]] = s[6]
                message['Payload'] = OrderedDict()
                for k in range(10, len(s)):
                    if k == 10:
                        message['Payload']['to_MLN'] = int(s[k], base=16)
                    if k == 11:
                        message['Payload']['Destination'] = self._dictsanitize(
                            CONST.destselectordict, int(s[k], base=16))
                    if k == 12:
                        message['Payload']['Command'] = self._dictsanitize(
                            CONST.beo4_commanddict, int(s[k], base=16)).upper()
                    if k == 13:
                        message['Payload']['Sec-Source'] = self._dictsanitize(
                            CONST.mlgw_secsourcedict, int(s[k], base=16))
                    if k == 14:
                        message['Payload']['Link'] = self._dictsanitize(
                            CONST.mlgw_linkdict, int(s[k], base=16))
                    if k > 14:
                        message['Payload']['cmd' + str(k - 9)] = self._dictsanitize(
                            CONST.beo4_commanddict, int(s[k], base=16))
        return message

    @staticmethod
    def _decode_action(telegram, message):
        message['Zone'] = telegram[0].upper()
        message['Room'] = telegram[1].upper()
        message['Type'] = telegram[2].upper()
        message['Device'] = telegram[3]
        message['State_Update'] = OrderedDict()
        if message.get('Type') == 'BUTTON':
            if telegram[4].split('=')[0] == '_SET STATE?STATE':
                message['State_Update']['STATE'] = telegram[4].split('=')[1]
                if message['State_Update'].get('STATE') == '0':
                    message['State_Update']['Status'] = "Off"
                else:
                    message['State_Update']['Status'] = "On"
            else:
                message['State_Update']['STATE'] = telegram[4]

        if message.get('Type') == 'DIMMER':  # e.g. DownstairsHallwayDIMMERWall LightSTATE_UPDATE?LEVEL=5
            if telegram[4].split('=')[0] == '_SET STATE?LEVEL':
                message['State_Update']['LEVEL'] = telegram[4].split('=')[1]
                if message['State_Update'].get('LEVEL') == '0':
                    message['State_Update']['Status'] = "Off"
                else:
                    message['State_Update']['Status'] = "On"
            else:
                message['State_Update']['STATE'] = telegram[4]
        return message

    @staticmethod
    def _decode_command(telegram, message):
        message['Zone'] = telegram[0].upper()
        message['Room'] = telegram[1].upper()
        message['Type'] = telegram[2].upper()
        message['Device'] = telegram[3]
        message['State_Update'] = OrderedDict()
        if message.get('Type') == 'BUTTON':
            if telegram[4].split('=')[0] == '_SET STATE?STATE':
                message['State_Update']['STATE'] = telegram[4].split('=')[1]
                if message['State_Update'].get('STATE') == '0':
                    message['State_Update']['Status'] = "Off"
                else:
                    message['State_Update']['Status'] = "On"
            else:
                message['State_Update']['STATE'] = telegram[4]

        if message.get('Type') == 'DIMMER':
            if telegram[4].split('=')[0] == '_SET STATE?LEVEL':
                message['State_Update']['LEVEL'] = telegram[4].split('=')[1]
                if message['State_Update'].get('LEVEL') == '0':
                    message['State_Update']['Status'] = "Off"
                else:
                    message['State_Update']['Status'] = "On"
            else:
                message['State_Update']['STATE'] = telegram[4]
        return message

    def _decode_trigger(self, telegram, message):
        message['Zone'] = telegram[0].upper()
        message['Room'] = telegram[1].upper()
        message['Type'] = telegram[2].upper()
        message['Device'] = telegram[3]
        message['State_Update'] = OrderedDict()

        if message.get('Type') == 'BUTTON':
            if telegram[4].split('=')[0] == 'STATE_UPDATE?STATE':
                message['State_Update']['STATE'] = telegram[4].split('=')[1]
                if message['State_Update'].get('STATE') == '0':
                    message['State_Update']['Status'] = "Off"
                else:
                    message['State_Update']['Status'] = "On"
            else:
                message['State_Update']['STATE'] = telegram[4]

        if message.get('Type') == 'DIMMER':
            if telegram[4].split('=')[0] == 'STATE_UPDATE?LEVEL':
                message['State_Update']['LEVEL'] = telegram[4].split('=')[1]
                if message['State_Update'].get('LEVEL') == '0':
                    message['State_Update']['Status'] = "Off"
                else:
                    message['State_Update']['Status'] = "On"
            else:
                message['State_Update']['STATE'] = telegram[4]

        if message.get('Type') == 'AV RENDERER':
            if telegram[4][:5] == 'Light':
                state = telegram[4][6:].split('&')
                message['State_Update']['type'] = 'Light Command'
                for s in state:
                    message['State_Update'][s.split('=')[0].lower()] = s.split('=')[1].title()
                    if message['State_Update'].get('command') == ' Cmd':
                        message['State_Update']['command'] = self._dictsanitize(CONST.beo4_commanddict,
                                                                                int(s[13:].strip())).title()
            elif telegram[4][:7] == 'Control':
                state = telegram[4][6:].split('&')
                message['State_Update']['type'] = 'Control Command'
                for s in state:
                    message['State_Update'][s.split('=')[0].lower()] = s.split('=')[1]
                    if message['State_Update'].get('command') == ' cmd':
                        message['State_Update']['command'] = self._dictsanitize(CONST.beo4_commanddict,
                                                                                int(s[13:].strip())).title()
            elif telegram[4] == 'All standby':
                message['State_Update']['command'] = telegram[4]

            else:
                state = telegram[4][13:].split('&')
                for s in state:
                    if s.split('=')[0] == 'sourceUniqueId':
                        src = s.split('=')[1].split(':')[0].upper()
                        message['State_Update']['source'] = self._srcdictsanitize(CONST.blgw_srcdict, src)
                        message['State_Update'][s.split('=')[0]] = s.split('=')[1]
                    elif s.split('=')[0] == 'nowPlayingDetails':
                        message['State_Update']['nowPlayingDetails'] = OrderedDict()
                        details = s.split('=')[1].split(';')
                        if len(details) > 1:
                            for d in details:
                                if d.split(':')[0].strip() in ['track number', 'channel number']:
                                    message['State_Update']['nowPlayingDetails']['channel_track'] \
                                        = d.split(':')[1].strip()
                                else:
                                    message['State_Update']['nowPlayingDetails'][d.split(':')[0].strip()] \
                                        = d.split(':')[1].strip()
                    else:
                        message['State_Update'][s.split('=')[0]] = s.split('=')[1]
        return message

    def _report(self, header, telegram, message):
        self.last_message = message
        self.log.debug(self.name + "\n" + str(json.dumps(message, indent=4)))
        if self.messageCallBack:
            self.messageCallBack(self.name, ''.join(header).upper(), ''.join(telegram), message)

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
        self._send_cmd(self._pwd)
        self._send_cmd("MONITOR")

    def handle_close(self):
        self.log.info(self.name + ": Closing socket")
        self.is_connected = False
        self.close()

    def _send_cmd(self, telegram):
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

    def toggle_events(self):
        try:
            self.push('e')
        except socket.error, e:
            self.log.info("Error sending data: %s" % e)
            self.handle_close()

    def toggle_macros(self):
        try:
            self.push('m')
        except socket.error, e:
            self.log.info("Error sending data: %s" % e)
            self.handle_close()

    def toggle_commands(self):
        try:
            self.push('c')
        except socket.error, e:
            self.log.info("Error sending data: %s" % e)
            self.handle_close()

    def ping(self):
        self._send_cmd('')

    # ########################################################################################
    # ##### Utility functions
    @staticmethod
    def _hexbyte(byte):
        resultstr = hex(byte)
        if byte < 16:
            resultstr = resultstr[:2] + "0" + resultstr[2]
        return resultstr

    def _dictsanitize(self, d, s):
        result = d.get(s)
        if result is None:
            result = "UNKNOWN (type=" + self._hexbyte(s) + ")"
        return str(result)

    @staticmethod
    def _srcdictsanitize(d, s):
        result = d.get(s)
        if result is None:
            result = s
        return str(result)
