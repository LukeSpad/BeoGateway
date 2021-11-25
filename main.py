import asyncore
import logging
import json
import time
from datetime import datetime

import Resources.MLCONFIG as MLCONFIG
import Resources.MLGW_CLIENT as MLGW
import Resources.MLCLI_CLIENT as MLCLI
import Resources.BLHIP_CLIENT as BLHIP
import Resources.MLtn_CLIENT as MLtn


if __name__ == '__main__':

    # Define callback function for JSON data dump from B&O Gateway
    def cb(name, header, payload, message):
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
        elif 73 < len(payload) + 9 < 132:
            logging.info("\n\t----------------------------------------------------------------------------" +
                         "\n\t" + name + ": <--Data-received!-<< " +
                         datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                         "\n\t----------------------------------------------------------------------------" +
                         "\n\tHeader: " + header +
                         "\n\tPayload: " + payload[:66] + "\n\t\t" + payload[66:132] +
                         "\n\t============================================================================" +
                         message)
        else:
            logging.info("\n\t----------------------------------------------------------------------------" +
                         "\n\t" + name + ": <--Data-received!-<< " +
                         datetime.now().strftime("on %d/%m/%y at %H:%M:%S") +
                         "\n\t----------------------------------------------------------------------------" +
                         "\n\tHeader: " + header +
                         "\n\tPayload: " + payload[:66] + "\n\t\t" + payload[66:132] + "\n\t\t" + payload[132:] +
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
    host = 'blgw.local'
    port = [9000, 9100, 23]
    user = 'admin'
    pwd = 's0198247'

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
