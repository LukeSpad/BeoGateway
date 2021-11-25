import asynchat
import logging
import socket
import time
import json
import urllib
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class BLHIPClient(asynchat.async_chat):
    """Client to interact with a Beolink Gateway via the Home Integration Protocol
    https://manualzz.com/download/14415327
    Full documentation of states, commands and events can be found in the driver development guide
    https://vdocument.in//blgw-driver-development-guide-blgw-driver-development-guide-7-2016-10-10"""
    def __init__(self, host_address='blgw.local', port=9100, user='admin', pwd='admin', name='BLGW_HIP', cb=None):
        asynchat.async_chat.__init__(self)
        self.log = logging.getLogger('Client (%7s)' % name)
        self.log.setLevel('INFO')

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
        self.log.debug(data)
        self._received_data += data

    def found_terminator(self):
        self.last_received = self._received_data
        self.last_received_at = time.time()
        self.log.debug(self._received_data)

        if self._received_data == 'error':
            self.handle_close()

        if self._received_data == 'e OK f%20%2A/%2A/%2A/%2A':
            self.log.info('\tAuthentication Successful!')
            self.query(dev_type="AV renderer")

        telegram = urllib.unquote(self._received_data)
        telegram = telegram.split('/')
        header = telegram[0:4]
        self._received_data = ""

        self._decode(header, telegram)

    def _decode(self, header, telegram):
        e_string = str(header[0])
        if e_string[0] == 'e':
            if e_string[2:4] == 'OK':
                self.log.info('Command Successfully Processed: ' + urllib.unquote(self._received_data))
            elif e_string[2:5] == 'CMD':
                self.log.info('Wrong or Unrecognised Command: ' + urllib.unquote(self._received_data))
                return
            elif e_string[2:5] == 'SYN':
                self.log.info('Bad Syntax, or Wrong Character Encoding: ' + urllib.unquote(self._received_data))
                return
            elif e_string[2:5] == 'ACC':
                self.log.info('Zone Access Violation: ' + urllib.unquote(self._received_data))
                return
            elif e_string[2:5] == 'LEN':
                self.log.info('Received Message Too Long: ' + urllib.unquote(self._received_data))
                return

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
            if 'nowPlayingDetails' in message['State_Update'] \
                    and message['State_Update']['nowPlayingDetails']['type'] == 'Legacy':
                self._get_channel_track(message)

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
        # Report messages, excluding regular clock pings from gateway
        self.last_message = message
        if message.get('Device').upper() != 'CLOCK':
            self.log.debug(self.name + "\n" + str(json.dumps(message, indent=4)))
            if self.messageCallBack:
                self.messageCallBack(self.name, str(list(header)), str(list(payload)), message)

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
        self.send_cmd(self._user)
        self.send_cmd(self._pwd)
        self.statefiler()

    def handle_close(self):
        self.log.info(self.name + ": Closing socket")
        self.is_connected = False
        self.close()

    def send_cmd(self, telegram):
        try:
            self.push(telegram.encode("ascii") + "\r\n")
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

        self.log.info(self.name + ": sending state update request for" + device + dev_type + room + zone)
        self.send_cmd(query)

    def statefiler(self, zone='*', room='*', dev_type='*', device='*'):
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

    @staticmethod
    def _get_channel_track(message):
        # Check device list for channel name information
        if CONST.devices:
            for device in CONST.devices:
                if device['Device'] == message['Device']:
                    if 'channels' in device['Sources'][message["State_Update"]["source"]]:
                        for channel in device['Sources'][message["State_Update"]["source"]]['channels']:
                            if channel['number'] == int(message["State_Update"]['nowPlayingDetails']["channel_track"]):
                                message["State_Update"]["nowPlaying"] = channel['name']
                                break
