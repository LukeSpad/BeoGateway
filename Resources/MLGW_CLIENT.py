import asynchat
import logging
import socket
import time
import json
from collections import OrderedDict

import Resources.CONSTANTS as const

class MLGWClient(asynchat.async_chat):
    """Client to interact with a B&O Gateway via the MasterLink Gateway Protocol
    http://mlgw.bang-olufsen.dk/source/documents/mlgw_2.24b/MlgwProto0240.pdf ."""

    def __init__(self, host_address='blgw.local', port=9000, user='admin', pwd='admin', name='MLGW_Protocol', cb=None):
        asynchat.async_chat.__init__(self)
        self.log = logging.getLogger('Client (%7s)' % name)
        self.log.setLevel('INFO')

        self._host = host_address
        self._port = int(port)
        self._user = user
        self._pwd  = pwd
        self.name = name
        self.is_connected = False

        self._received_data = bytearray()
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

        #Expose dictionaries via API
        self.BEO4_CMDS = const.BEO4_CMDS
        self.CMDS_DEST = const.CMDS_DEST
        self.MLGW_PL = const.MLGW_PL

        # ########################################################################################
        # ##### Open Socket and connect to B&O Gateway
        self.client_connect()

    # ########################################################################################
    # ##### Client functions
    def collect_incoming_data(self, data):
        self.is_connected = True
        self.log.debug(data)
        self._received_data = bytearray(data)

        bit1 = int(self._received_data[0])       #Start of Header == 1
        bit2 = int(self._received_data[1])       #Message Type
        bit3 = int(self._received_data[2])       #Payload length
        bit4 = int(self._received_data[3])       #Spare Bit/End of Header == 0

        payload = bytearray()
        for item in self._received_data[4:bit3 + 4]:
            payload.append(item)

        if bit1 == 1 and len(self._received_data) == bit3 + 4 and bit4 == 0:
            self.found_terminator(bit2, payload)
        else:
            self.log.info("Incomplete Telegram Received: " + str(list(self._received_data)) + " - Ignoring!\n")

    def found_terminator(self, msg_type, payload):
        self.last_received = str(list(self._received_data))
        self.last_received_at = time.time()
        self.log.debug(self._received_data)

        header = self._received_data[0:4]
        self._received_data = ""
        self._decode(msg_type, header, payload)

    def _decode(self, msg_type, header, payload):
        message = OrderedDict()
        payload_type = self._dictsanitize(const._mlgw_payloadtypedict, msg_type)
        message["Payload_type"] = payload_type

        if payload_type == "MLGW virtual button event":
            virtual_btn = payload[0]
            if len(payload) < 1:
                virtual_action = self._getvirtualactionstr(0x01)
            else:
                virtual_action = self._getvirtualactionstr(payload[1])

            message["button"] = virtual_btn
            message["action"] = virtual_action

        elif payload_type == "Login status":
            if payload == 0:
                self.log.info("\tAuthentication Failed: MLGW protocol Password required for %s", self._host)
                self.handle_close()
                message['Connected'] = "False"
                return
            else:
                self.log.info("\tLogin successful to %s", self._host)
                self.is_connected = True
                message['Connected'] = "True"
                self.get_serial()

        elif payload_type == "Pong":
                self.is_connected = True
                message['CONNECTION'] = 'Online'

        elif payload_type == "Serial Number":
            sn = ''
            for c in payload:
                sn += chr(c)
            message['Serial_Num'] = sn

        elif payload_type == "Source Status":
            if const.rooms and const.devices:
                for device in const.devices:
                    if device['MLN'] == payload[0]:
                        name = device['Device']
                        for room in const.rooms:
                            if name in room['Products']:
                                message["Zone"] = room['Zone'].upper()
                                message["Room"] = room['Room_Name'].upper()
                                message["Type"] = 'AV RENDERER'
                                message["Device"] = name

            message["MLN"] = payload[0]
            message["Source"] = self._getselectedsourcestr(payload[1]).upper()
            message["Source_medium_position"] = self._hexword(payload[2], payload[3])
            message["Source_position"] = self._hexword(payload[4], payload[5])
            message["Picture_format"] = self._getdictstr(const.ml_pictureformatdict, payload[7])
            message["State"] = self._getdictstr(const._sourceactivitydict, payload[6])

        elif payload_type == "Picture and Sound Status":
            if const.rooms and const.devices:
                for device in const.devices:
                    if device['MLN'] == payload[0]:
                        name = device['Device']
                        for room in const.rooms:
                            if name in room['Products']:
                                message["Zone"] = room['Zone'].upper()
                                message["Room"] = room['Room_Name'].upper()
                                message["Type"] = 'AV RENDERER'
                                message["Device"] = name

            message["MLN"] = payload[0]
            message["Sound_status"] = self._getdictstr(const.mlgw_soundstatusdict, payload[1])
            message["Speaker_mode"] = self._getdictstr(const._mlgw_speakermodedict, payload[2])
            message["Stereo_mode"] = self._getdictstr(const._mlgw_stereoindicatordict, payload[9])
            message["Volume"] = int(payload[3])
            message["Screen1_mute"] = self._getdictstr(const._mlgw_screenmutedict, payload[4])
            message["Screen1_active"] = self._getdictstr(const._mlgw_screenactivedict, payload[5])
            message["Screen2_mute"] = self._getdictstr(const._mlgw_screenmutedict, payload[6])
            message["Screen2_active"] = self._getdictstr(const._mlgw_screenactivedict, payload[7])
            message["Cinema_mode"] = self._getdictstr(const._mlgw_cinemamodedict, payload[8])


        elif payload_type == "All standby notification":
            message["Command"] = "All Standby"

        elif payload_type == "Light and Control command":
            if const.rooms:
                for room in const.rooms:
                    if room['Room_Number'] == payload[0]:
                        message["Zone"] = room['Zone'].upper()
                        message["Room"] = room['Room_Name'].upper()
            message["Type"] = self._getdictstr(const._mlgw_lctypedict, payload[1]).upper() + " COMMAND"
            message["Device"] = 'Beo4/BeoRemote One'
            message["Room number"] = str(payload[0])
            message["Command"] = self._getbeo4commandstr(payload[2])

        if message != '':
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
        login=[]
        for c in self._user:
            login.append(c)
        login.append(0x00)
        for c in self._pwd:
            login.append(c)

        self.log.info("\tAttempting to Authenticate...")
        self._send_cmd(const.MLGW_PL.get("LOGIN REQUEST"), login)

    def handle_close(self):
        self.log.info(self.name + ": Closing socket")
        self.is_connected = False
        self.close()

    def _report(self, header, payload, message):
        self.last_message = message
        self.log.debug(self.name + "\n" + str(json.dumps(message, indent=4)))
        if self.messageCallBack:
            self.messageCallBack(self.name, str(list(header)), str(list(payload)), message)

    # ########################################################################################
    # ##### mlgw send_cmder functions

     ## send_cmd command to mlgw
    def _send_cmd(self, msg_type, payload):
        #construct header
        telegram = [1,msg_type,len(payload),0]
        #append payload
        for p in payload:
            telegram.append(p)

        try:
            self.push(str(bytearray(telegram)))
        except socket.error, e:
            self.log.info("Error sending data: %s" % e)
            self.handle_close()
        except socket.timeout, e:
            self.log.info("\tSocket connection to %s:%i timed out- %s" % (self._host, self._port, e))
            self.handle_close()
        else:
            self.last_sent = str(bytearray(telegram))
            self.last_sent_at = time.time()
            self.log.info(
                self.name + " >>-SENT--> "
                + self._getpayloadtypestr(msg_type)
                + ": "
                + str(list(telegram))
            )

            # Sleep to allow msg to arrive
            time.sleep(0.2)

    def ping(self):
        self._send_cmd(const.MLGW_PL.get("PING"), "")

    ## Get serial number of mlgw
    def get_serial(self):
        if self.is_connected:
            # Request serial number
            self._send_cmd(const.MLGW_PL.get("REQUEST SERIAL NUMBER"), "")

    ## send_cmd Beo4 command to mlgw
    def send_beo4_cmd(self, mln, dest, cmd, sec_source=0x00, link=0x00):
        payload = []
        payload.append(mln)           # byte[0] MLN
        payload.append(dest)          # byte[1] Dest-Sel (0x00, 0x01, 0x05, 0x0f)
        payload.append(cmd)           # byte[2] Beo4 Command
        payload.append(sec_source)    # byte[3] Sec-Source
        payload.append(link)          # byte[4] Link
        self._send_cmd(const.MLGW_PL.get("BEO4 COMMAND"), payload)

    ## send_cmd BeoRemote One command to mlgw
    def send_beoremoteone_cmd(self, mln, cmd, network_bit=0x00):
        payload = []
        payload.append(mln)           # byte[0] MLN
        payload.append(cmd)           # byte[1] Beo4 Command
        payload.append(0x00)          # byte[2] AV (needs to be 0)
        payload.append(network_bit)   # byte[3] Network_bit (0 = local source, 1 = network source)
        self._send_cmd(const.MLGW_PL.get("BEOREMOTE ONE CONTROL COMMAND"), payload)

    ## send_cmd BeoRemote One Source Select to mlgw
    def send_beoremoteone_select_source(self, mln, cmd, unit, network_bit=0x00):
        payload = []
        payload.append(mln)           # byte[0] MLN
        payload.append(cmd)           # byte[1] Beormyone Command
        payload.append(unit)          # byte[2] Unit
        payload.append(0x00)          # byte[3] AV (needs to be 0)
        payload.append(network_bit)   # byte[4] Network_bit (0 = local source, 1 = network source)
        self._send_cmd(const.MLGW_PL.get("BEOREMOTE ONE SOURCE SELECTION"), payload)

    ## send_cmd Beo4 commmand and store the source name
    def send_beo4_select_source(self, mln, dest, source, sec_source=0x00, link=0x00):
        beolink_source = self._dictsanitize(const.beo4_commanddict, source).upper()
        self.send_beo4_cmd(mln, dest, source, sec_source, link)

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
            result = "UNKNOWN (type=" + self._hexbyte(s) + ")"
        return str(result)

    # ########################################################################################
    # ##### Decode MLGW Protocol packet to readable string

    ## Get message string for mlgw packet's payload type
    #
    def _getpayloadtypestr(self, payloadtype):
        result = const._mlgw_payloadtypedict.get(payloadtype)
        if result == None:
            result = "UNKNOWN (type=" + self._hexbyte(payloadtype) + ")"
        return str(result)

    def _getmlnstr(self, mln):
        result = "MLN=" + str(mln)
        return result

    def _getbeo4commandstr(self, command):
        result = const.beo4_commanddict.get(command)
        if result == None:
            result = "Cmd=" + self._hexbyte(command)
        return result

    def _getvirtualactionstr(self, action):
        result = const._mlgw_virtualactiondict.get(action)
        if result == None:
            result = "Action=" + self._hexbyte(action)
        return result

    def _getselectedsourcestr(self, source):
        result = const.ml_selectedsourcedict.get(source)
        if result == None:
            result = "Src=" + self._hexbyte(source)
        return result

    def _getspeakermodestr(self, source):
        result = const._mlgw_speakermodedict.get(source)
        if result == None:
            result = "mode=" + self._hexbyte(source)
        return result

    def _getdictstr(self, mydict, mykey):
        result = mydict.get(mykey)
        if result == None:
            result = self._hexbyte(mykey)
        return result