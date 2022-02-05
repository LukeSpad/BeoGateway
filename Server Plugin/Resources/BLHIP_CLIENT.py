import indigo
import asynchat
import socket
import time
import urllib
import logging
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class BLHIPClient(asynchat.async_chat):
    """Client to interact with a Beolink Gateway via the Home Integration Protocol
    https://manualzz.com/download/14415327
    Full documentation of states, commands and events can be found in the driver development guide
    https://vdocument.in//blgw-driver-development-guide-blgw-driver-development-guide-7-2016-10-10"""
    def __init__(self, host_address='blgw.local', port=9100, user='admin', pwd='admin', name='BLGW_HIP',
                 debug=False, cb=None):
        asynchat.async_chat.__init__(self)

        self.debug = debug

        self._host = host_address
        self._port = int(port)
        self._user = user
        self._pwd = pwd
        self.name = name
        self.is_connected = False

        self._received_data = ''
        self.last_sent = ''
        self.last_sent_at = time.time()
        self.last_received = ''
        self.last_received_at = time.time()
        self.last_message = {}

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
        self.is_connected = True
        self._received_data += data

    def found_terminator(self):
        # indigo.server.log("Raw Data: " + self._received_data)
        self.last_received = self._received_data
        self.last_received_at = time.time()

        if self._received_data == 'error':
            self.handle_close()

        if self._received_data == 'e OK f%20%2A/%2A/%2A/%2A':
            indigo.server.log('\tAuthentication Successful!', level=logging.DEBUG)
            self.query(dev_type="AV renderer")

        self._received_data = urllib.unquote(self._received_data)
        telegram = self._received_data.replace("%201", "")
        telegram = telegram.split('/')
        header = telegram[0:4]

        self._decode(header, telegram)

    def _decode(self, header, telegram):
        e_string = str(header[0])
        if e_string[0] == 'e':
            if e_string[2:4] == 'OK' and self.debug:
                indigo.server.log('Command Successfully Processed: ' + str(urllib.unquote(self._received_data)),
                                  level=logging.DEBUG)

            elif e_string[2:5] == 'CMD':
                indigo.server.log('Wrong or Unrecognised Command: ' + str(urllib.unquote(self._received_data)),
                                  level=logging.WARNING)

            elif e_string[2:5] == 'SYN':
                indigo.server.log('Bad Syntax, or Wrong Character Encoding: ' +
                                  str(urllib.unquote(self._received_data)), level=logging.WARNING)

            elif e_string[2:5] == 'ACC':
                indigo.server.log('Zone Access Violation: ' + str(urllib.unquote(self._received_data)),
                                  level=logging.WARNING)

            elif e_string[2:5] == 'LEN':
                indigo.server.log('Received Message Too Long: ' + str(urllib.unquote(self._received_data)),
                                  level=logging.WARNING)

            self._received_data = ""
            return
        else:
            self._received_data = ""

        if len(telegram) > 4:
            state = telegram[4].replace('?', '&')
            state = state.split('&')[1:]

            message = OrderedDict()
            message['Zone'] = telegram[0][2:].upper()
            message['Room'] = telegram[1].upper()
            message['Type'] = telegram[2].upper()
            message['Device'] = telegram[3]
            message['State_Update'] = OrderedDict()

            for s in state:
                if s.split('=')[0] == "nowPlayingDetails":
                    play_details = s.split('=')
                    if len(play_details[1]) > 0:
                        play_details = play_details[1].split('; ')
                        message['State_Update']["nowPlayingDetails"] = OrderedDict()
                        for p in play_details:
                            if p.split(': ')[0] in ['track number', 'channel number']:
                                message['State_Update']["nowPlayingDetails"]['channel_track'] = p.split(': ')[1]
                            else:
                                message['State_Update']["nowPlayingDetails"][p.split(': ')[0]] = p.split(': ')[1]

                elif s.split('=')[0] == "sourceUniqueId":
                    src = s.split('=')[1].split(':')[0].upper()
                    message['State_Update']['source'] = self._srcdictsanitize(CONST.blgw_srcdict, src)
                    message['State_Update'][s.split('=')[0]] = s.split('=')[1]
                else:
                    message['State_Update'][s.split('=')[0]] = s.split('=')[1]

            # call function to find channel details if type = Legacy
            try:
                if 'nowPlayingDetails' in message['State_Update'] \
                        and message['State_Update']['nowPlayingDetails']['type'] == 'Legacy':
                    self._get_channel_track(message)
            except KeyError:
                pass

            if message.get('Type') == 'BUTTON':
                if message['State_Update'].get('STATE') == '0':
                    message['State_Update']['Status'] = 'Off'
                else:
                    message['State_Update']['Status'] = 'On'

            if message.get('Type') == 'DIMMER':
                if message['State_Update'].get('LEVEL') == '0':
                    message['State_Update']['Status'] = 'Off'
                else:
                    message['State_Update']['Status'] = 'On'

            self._report(header, state, message)

    def _report(self, header, payload, message):
        self.last_message = message
        if self.messageCallBack:
            self.messageCallBack(self.name, str(list(header)), str(list(payload)), message)

    def client_connect(self):
        indigo.server.log('Connecting to host at ' + self._host + ', port ' + str(self._port), level=logging.WARNING)
        self.set_terminator(b'\r\n')
        # Create the socket
        try:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, e:
            indigo.server.log("Error creating socket: " + str(e), level=logging.ERROR)
            self.handle_close()
        # Now connect
        try:
            self.connect((self._host, self._port))
        except socket.gaierror, e:
            indigo.server.log("\tError with address: " + str(e), level=logging.ERROR)
            self.handle_close()
        except socket.timeout, e:
            indigo.server.log("\tSocket connection timed out: " + str(e), level=logging.ERROR)
            self.handle_close()
        except socket.error, e:
            indigo.server.log("\tError opening connection: " + str(e), level=logging.ERROR)
            self.handle_close()
        else:
            self.is_connected = True
            indigo.server.log("\tConnected to B&O Gateway", level=logging.DEBUG)

    def handle_connect(self):
        indigo.server.log("\tAttempting to Authenticate...", level=logging.WARNING)
        self.send_cmd(self._user)
        self.send_cmd(self._pwd)
        self.statefilter()

    def handle_close(self):
        indigo.server.log(self.name + ": Closing socket", level=logging.ERROR)
        self.is_connected = False
        self.close()

    def send_cmd(self, telegram):
        try:
            self.push(telegram.encode("ascii") + "\r\n")
        except socket.timeout, e:
            indigo.server.log("\tSocket connection timed out: " + str(e), level=logging.ERROR)
            self.handle_close()
        except socket.error, e:
            indigo.server.log("Error sending data: " + str(e), level=logging.ERROR)
            self.handle_close()
        else:
            self.last_sent = telegram
            self.last_sent_at = time.time()
            if telegram == 'q Main/global/SYSTEM/BeoLink':
                if self.debug:
                    indigo.server.log(self.name + " >>-SENT--> : " + telegram, level=logging.DEBUG)
            else:
                indigo.server.log(self.name + " >>-SENT--> : " + telegram, level=logging.INFO)
            time.sleep(0.2)

    def query(self, zone='*', room='*', dev_type='*', device='*'):
        query = "q " + zone + "/" + room + "/" + dev_type + '/' + device

        # Convert to human readable string
        if zone == '*':
            zone = ' in all zones.'
        else:
            zone = ' in zone ' + zone + '.'
        if room == '*':
            room = ' in all rooms'
        else:
            room = ' in room ' + room
        if dev_type == '*':
            dev_type = ' of all types'
        else:
            dev_type = ' of type ' + dev_type
        if device == '*':
            device = ' all devices'
        else:
            device = ' devices called ' + device

        if self.debug:
            indigo.server.log(self.name + ": sending state update request for" + device + dev_type + room + zone,
                              level=logging.DEBUG)
        self.send_cmd(query)

    def statefilter(self, zone='*', room='*', dev_type='*', device='*'):
        s_filter = "f " + zone + "/" + room + "/" + dev_type + '/' + device
        self.send_cmd(s_filter)

    def locationevent(self, event):
        if event in ['leave', 'arrive']:
            event = 'l ' + event
            self.send_cmd(event)

    def ping(self):
        self.query('Main', 'global', 'SYSTEM', 'BeoLink')

    # Utility Functions
    @staticmethod
    def _srcdictsanitize(d, s):
        result = d.get(s)
        if result is None:
            result = s
        return str(result)

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
