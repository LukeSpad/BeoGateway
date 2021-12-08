import asyncore
import logging
import json
import time
from datetime import datetime

import Resources.CONSTANTS as CONST
import Resources.MLCONFIG as MLCONFIG
import Resources.MLGW_CLIENT as MLGW
import Resources.MLCLI_CLIENT as MLCLI
import Resources.BLHIP_CLIENT as BLHIP
import Resources.MLtn_CLIENT as MLtn
import Resources.ASBridge as ASBridge


if __name__ == '__main__':

    # Define callback function for JSON data dump from B&O Gateway
    def cb(name, header, payload, message):
        # Report message content to log
        message_log(name, header, payload, message)

        # If State Update received then post update in Notification Center
        notify_and_update(message)

        try:    # Transport controls for N.MUSIC iTunes control
            if message['State_Update']['source'] == "A.TAPE2/N.MUSIC":
                iTunes_transport_control(message)
            elif message['State_Update']['source'] != "A.TAPE2/N.MUSIC":
                iTunes.stop()
        except KeyError:
            pass

    def notify_and_update(message):
        # Post Source change information to Notification Center
        try:
            current_source = str(message['State_Update']['source'])

            # Check to see if this is a new Music Source notification
            if current_source in CONST.source_type_dict.get("Audio Sources"):
                update_devices(message, current_source, 'Audio Source')
                if current_source not in ['', CONST.gateway['Current Audio Source']]:
                    CONST.gateway['Current Audio Source'] = current_source
                    iTunes.notify("Current Audio Source: " + str(message['State_Update']['sourceName']))

            # Check to see if this is a new Video Source notification
            elif current_source in CONST.source_type_dict.get("Video Sources"):
                update_devices(message, current_source, 'Video Source')
                if current_source not in ['', CONST.gateway['Current Video Source']]:
                    CONST.gateway['Current Video Source'] = current_source
                    iTunes.notify("Current Video Source: " + str(message['State_Update']['sourceName']))

            # If source is not in Audio or Video dictionaries then it's a standby message
            else:
                update_devices(message, current_source, 'No Source')
        except KeyError:
            pass

    def update_devices(message, current_source, source_type):
        # Loop over devices to find device sending update message
        for device in CONST.devices:
            try:
                if str(message['Device']) == device['Device']:
                    # Filter for device status update after entering standby -
                    # not sure why this happens but it does sometimes
                    if device['State'] == 'Standby' and time.time() - device['last update'] < 1.0:
                        return

                    # If in standby, set current source to None
                    elif message['State_Update']['state'] in ['', 'Standby'] or \
                            message['State_Update']['source'] == '':
                        if device['State'] != 'Standby':
                            iTunes.notify(str(device['Device']) + " is now on standby")
                            device['State'] = 'Standby'
                            device['Now Playing'] = 'None'
                            device['Current Source'] = 'None'
                            device['last update'] = time.time()

                    # Report player state and source
                    elif message['State_Update']['state'] in ["None", "Play"]:
                        if message['State_Update']['nowPlaying'] not in ['', 'Unknown'] and \
                                message['State_Update']['nowPlaying'] != device['Now Playing']:
                            iTunes.notify(str(device['Device']) + " now playing " +
                                          str(message['State_Update']['nowPlaying']) + " from source " +
                                          str(message['State_Update']['sourceName']))
                            # Update device data
                            device['Now Playing'] = message['State_Update']['nowPlaying']
                            device['Channel/Track'] = '0'
                            device['last update'] = time.time()

                        elif 'nowPlayingDetails' in message['State_Update'] and \
                                message['State_Update']['nowPlaying'] in ['', 'Unknown'] and \
                                message['State_Update']['nowPlayingDetails']['channel_track'] \
                                not in [device['Channel/Track'], '0', '255']:
                            if source_type == "Audio Source":
                                iTunes.notify(str(device['Device']) + " now playing track " +
                                              str(message['State_Update']['nowPlayingDetails']['channel_track']) +
                                              " from source " + str(message['State_Update']['sourceName']))
                            elif source_type == "Video Source":
                                iTunes.notify(str(device['Device']) + " now playing channel " +
                                              str(message['State_Update']['nowPlayingDetails']['channel_track']) +
                                              " from source " + str(message['State_Update']['sourceName']))
                            # Update device data
                            device['Now Playing'] = 'Unknown'
                            device['Channel/Track'] = message['State_Update']['nowPlayingDetails']['channel_track']
                            device['last update'] = time.time()

                        elif message['State_Update']['state'] != device['State']:
                            iTunes.notify(str(device['Device']) + " is now playing " +
                                          str(message['State_Update']['sourceName']))
                            # Update device data
                            device['Now Playing'] = "Unknown"
                            device['Channel/Track'] = '0'
                            device['last update'] = time.time()

                        # Update the state of the device
                        device['Current Source'] = current_source
                        device['Current Source Type'] = source_type
                        device['State'] = message['State_Update']['state']

                        logging.debug(json.dumps(device, indent=4))
            except KeyError:
                pass

            # Now loop over devices and update any playing an audio source with the new distributed
            # source (the masterlink network only supports a single audio source for distribution)
            if source_type == "Audio Source":
                if device['Current Source'] in CONST.source_type_dict.get("Audio Sources"):
                    device['Current Source'] = current_source

    def iTunes_transport_control(message):
        try:    # If N.MUSIC command, trigger appropriate iTunes control
            if message['State_Update']['state'] not in ["", "Standby"]:
                iTunes.play()
        except KeyError:
            pass

        try:    # If N.MUSIC selected and Beo4 command received then run appropriate transport commands
            if message['State_Update']['command'] == "Go/Play":
                iTunes.play()

            elif message['State_Update']['command'] == "Stop":
                iTunes.pause()

            elif message['State_Update']['command'] == "Exit":
                iTunes.stop()

            elif message['State_Update']['command'] == "Step Up":
                iTunes.next_track()

            elif message['State_Update']['command'] == "Step Down":
                iTunes.previous_track()

            elif message['State_Update']['command'] == "Wind":
                iTunes.wind(10)

            elif message['State_Update']['command'] == "Rewind":
                iTunes.rewind(-10)

            # If 'Info' pressed - update track info
            elif message['State_Update']['command'] == "Info":
                track_info = iTunes.get_current_track_info()
                logging.info("iTunes current Track Info:"
                             "\n\tTrack: " + track_info[0] +
                             "\n\tAlbum: " + track_info[1] +
                             "\n\tArtist: " + track_info[2] + "\n")
                iTunes.notify("iTunes playing " + track_info[2] + " - " + track_info[0] +
                              " from album: " + track_info[1])

            # If colour key pressed, execute the appropriate applescript
            elif message['State_Update']['command'] == "Green":
                # Play a specific playlist - defaults to Recently Played
                script = ASBridge.__file__[:-12] + 'Scripts/green.scpt'
                iTunes.run_script(script)

            elif message['State_Update']['command'] == "Yellow":
                # Play a specific playlist - defaults to Recently Added
                script = ASBridge.__file__[:-12] + 'Scripts/yellow.scpt'
                iTunes.run_script(script)

            elif message['State_Update']['command'] == "Blue":
                # Play the current album
                script = ASBridge.__file__[:-12] + 'Scripts/blue.scpt'
                iTunes.run_script(script)

            elif message['State_Update']['command'] in ["0xf2", "Red", "MOTS"]:
                # More of the same (start a playlist with just current track and let autoplay find similar tunes)
                script = ASBridge.__file__[:-12] + 'Scripts/red.scpt'
                iTunes.run_script(script)
        except KeyError:
            pass

    def message_log(name, header, payload, message):
        # Pretty formatting - convert to JSON format then remove braces
        message = json.dumps(message, indent=4)
        for r in (('"', ''), (',', ''), ('{', ''), ('}', '')):
            message = str(message).replace(*r)

        # Print message data
        if len(payload) + 9 < 73:
            logging.info("\n\t----------------------------------------------------------------------------" +
                         "\n\t" + name + ": <--Data-received!-<< " +
                         datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                         "\n\t----------------------------------------------------------------------------" +
                         "\n\tHeader: " + header +
                         "\n\tPayload: " + payload +
                         "\n\t============================================================================" +
                         message)
        elif 73 < len(payload) + 9 < 137:
            logging.info("\n\t----------------------------------------------------------------------------" +
                         "\n\t" + name + ": <--Data-received!-<< " +
                         datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                         "\n\t----------------------------------------------------------------------------" +
                         "\n\tHeader: " + header +
                         "\n\tPayload: " + payload[:66] + "\n\t\t" + payload[66:137] +
                         "\n\t============================================================================" +
                         message)
        else:
            logging.info("\n\t----------------------------------------------------------------------------" +
                         "\n\t" + name + ": <--Data-received!-<< " +
                         datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                         "\n\t----------------------------------------------------------------------------" +
                         "\n\tHeader: " + header +
                         "\n\tPayload: " + payload[:66] + "\n\t\t" + payload[66:137] + "\n\t\t" + payload[137:] +
                         "\n\t============================================================================" +
                         message)

    def check_connection(self):
        last = round(time.time() - self.last_received_at, 2)
        logging.debug(self.name + " Protocol Client last received " + str(last) + " seconds ago")
        # Recconect if socket has disconnected, or if no response received to last ping
        if not self.is_connected or last > 60:
            logging.info("\t" + self.name + ": Reconnecting!")
            self.handle_close()
            time.sleep(0.5)
            self.client_connect()

    # ########################################################################################
    # Main program loop
    host = 'blgw.local'  # Host address of gateway
    port = [9000,        # MLGW protocol port - default 9000
            9100,        # BLGW Home Integration Protocol port - default 9100
            23]          # Telnet port - default 23
    user = 'admin'       # User name - default is admin
    pwd = 'admin'        # password - default is admin

    # Instantiate an AppleScriptBridge MusicController for N.MUSIC control of apple Music
    iTunes = ASBridge.MusicController()

    logging.basicConfig(level=logging.INFO)
    config = MLCONFIG.MLConfig(host, user, pwd)

    # Create MLGW Protocol and ML_CLI Protocol clients (basic command listening)
    logging.info('Creating MLGW Protocol Client...')
    mlgw = MLGW.MLGWClient(host, port[0], user, pwd, 'MLGW protocol', cb)
    asyncore.loop(count=10, timeout=0.2)

    logging.info('Creating ML Command Line Protocol Client...')
    mlcli = MLCLI.MLCLIClient(host, port[2], user, pwd, 'ML command line interface', cb)
    # Log onto the MLCLI client and ascertain the gateway model
    asyncore.loop(count=10, timeout=0.2)

    # Now MLGW and MasterLink Command Line Client are set up, retrieve MasterLink IDs of products
    config.get_masterlink_id(mlgw, mlcli)

    # If the gateway is a BLGW use the BLHIP protocol, else use the legacy MLHIP protocol
    if mlcli.isBLGW:
        logging.info('Creating BLGW Home Integration Protocol Client...')
        blgw = BLHIP.BLHIPClient(host, port[1], user, pwd, 'BLGW Home Integration Protocol', cb)
        mltn = None
    else:
        logging.info('Creating MLGW Home Integration Protocol Client...')
        mltn = MLtn.MLtnClient(host, port[2], user, pwd, 'ML telnet client', cb)
        blgw = None

    # Main program loop
    while True:
        # Ping all connections every 10 minutes to prompt messages on the network
        asyncore.loop(count=595, timeout=1)
        if mlgw.is_connected:
            mlgw.ping()
        if mlcli.is_connected:
            mlcli.ping()
        if mlcli.isBLGW:
            if blgw.is_connected:
                blgw.ping()
        else:
            if mltn.is_connected:
                mltn.ping()

        # Check the connections approximately every 10 minutes to keep sockets open
        asyncore.loop(count=5, timeout=1)
        logging.debug("LOOP: %d enqueued, waiting to finish!" % len(asyncore.socket_map))
        check_connection(mlgw)
        check_connection(mlcli)
        if mlcli.isBLGW:
            check_connection(blgw)
        else:
            check_connection(mltn)
