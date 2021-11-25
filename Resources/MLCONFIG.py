import logging
import requests
import asyncore
import json
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class MLConfig:

    def __init__(self, host_address='blgw.local', user='admin', pwd='admin'):
        self.log = logging.getLogger('Config')
        self.log.setLevel('INFO')

        self._host = host_address
        self._user = user
        self._pwd = pwd

        self._download_data()

    def _download_data(self):
        self.log.info('Downloading configuration data from Gateway...')
        url = 'http://' + self._host + '/mlgwpservices.json'
        auth = (self._user, self._pwd)
        response = requests.get(url, auth=auth)
        configurationdata = json.loads(response.text)
        self.configure_mlgw(configurationdata)

    def configure_mlgw(self, data):
        self.log.info('Processing Gateway configuration data...\n')
        CONST.gateway['Serial_Number'] = data['sn']
        CONST.gateway['Project'] = data['project']
        CONST.gateway['Installer'] = str(data['installer']['name'])
        CONST.gateway['Contact'] = str(data['installer']['contact'])

        for zone in data["zones"]:
            if int(zone['number']) == 240:
                continue
            room = OrderedDict()
            room['Room_Number'] = zone['number']
            room['Zone'] = str(zone['name']).split('/')[0]
            room['Room_Name'] = str(zone['name']).split('/')[1]
            room['Products'] = []

            for product in zone["products"]:
                device = OrderedDict()
                room['Products'].append(str(product["name"]))
                device['Device'] = str(product["name"])
                device['MLN'] = product["MLN"]
                device['ML_ID'] = ''
                device['Serial_num'] = str(product["sn"])
                device['Zone'] = str(zone["name"]).split('/')[0]
                device['Room'] = str(zone["name"]).split('/')[1]
                device['Room_Number'] = str(zone["number"])
                device['Sources'] = OrderedDict()

                for source in product["sources"]:
                    device['Sources'][str(source["name"])] = OrderedDict()
                    for selectCmd in source["selectCmds"]:
                        source_id = str(source['sourceId'].split(':')[0])
                        source_id = self._srcdictsanitize(CONST.blgw_srcdict, source_id).upper()
                        device['Sources'][str(source["name"])]['source'] = source_id
                        device['Sources'][str(source["name"])]['uniqueID'] = str(source['sourceId'])
                        source_tuple = (str(source["name"]), source_id)
                        cmd_tuple = (source_id, (int(selectCmd["cmd"]), int(selectCmd["unit"])))
                        device['Sources'][str(source["name"])]['BR1_cmd'] = cmd_tuple
                        if 'channels' in source:
                            device['Sources'][str(source["name"])]['channels'] = []
                            for channel in source['channels']:
                                c = OrderedDict()
                                c_num = ''
                                num = channel['selectSEQ'][::2]
                                for n in num:
                                    c_num += str(n)
                                c['number'] = int(c_num)
                                c['name'] = channel['name']
                                c['icon'] = channel['icon']
                                device['Sources'][str(source["name"])]['channels'].append(c)

                        if source_tuple not in CONST.available_sources:
                            CONST.available_sources.append(source_tuple)

                CONST.devices.append(device)
            CONST.rooms.append(room)

        self.log.info('Found ' + str(len(CONST.devices)) + ' AV Renderers!')
        for i in range(len(CONST.devices)):
            self.log.info('\tMLN ' + str(CONST.devices[i].get('MLN')) + ': ' + str(CONST.devices[i].get('Device')))
        self.log.info('\tFound ' + str(len(CONST.available_sources)) + ' Available Sources [Name, Type]:')
        for i in range(len(CONST.available_sources)):
            self.log.info('\t\t' + str(list(CONST.available_sources[i])))
        self.log.info('Done!\n')

        self.log.debug(json.dumps(CONST.gateway, indent=4))
        self.log.debug(json.dumps(CONST.rooms, indent=4))
        self.log.debug(json.dumps(CONST.devices, indent=4))

    def get_masterlink_id(self, mlgw, mlcli):
        self.log.info("Finding MasterLink ID of products:")
        if mlgw.is_connected and mlcli.is_connected:
            for device in CONST.devices:
                self.log.info("Finding MasterLink ID of product " + device.get('Device'))
                # Ping the device with a light timeout to elicit a ML telegram containing its ML_ID
                mlgw.send_beo4_cmd(int(device.get('MLN')),
                                   CONST.CMDS_DEST.get("AUDIO SOURCE"),
                                   CONST.BEO4_CMDS.get("LIGHT TIMEOUT"))

                if device.get('Serial_num') is None:
                    # If this is a MasterLink product it has no serial number...
                    # loop to until expected response received from ML Command Line Interface
                    while 'to_device' not in mlcli.last_message and mlcli.last_message['from_device'] == \
                            "MLGW" and mlcli.last_message['payload_type'] == \
                            "MLGW_REMOTE_BEO4" and mlcli.last_message['payload']['command'] == "LIGHT TIMEOUT":
                        asyncore.loop(count=1, timeout=0.2)

                    device['ML_ID'] = mlcli.last_message.get('to_device')
                    self.log.info("\tMasterLink ID of product " + 
                                  device.get('Device') + " is " + device.get('ML_ID') + ".\n")
                else:
                    # If this is a NetLink product then it has a serial number and no ML_ID
                    device['ML_ID'] = 'NA'
                    self.log.info("\tNetworkLink ID of product " + device.get('Device') + " is " + 
                                  device.get('Serial_num') + ". No MasterLink ID assigned.\n")

    @staticmethod
    def _srcdictsanitize(d, s):
        result = d.get(s)
        if result is None:
            result = s
        return str(result)
