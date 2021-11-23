import logging
import requests
import asyncore
import json
from collections import OrderedDict

import Resources.CONSTANTS as const

class MLConfig:

    def __init__(self, host_address='blgw.local', user='admin', pwd='admin'):
        self.log = logging.getLogger('Config:')
        self.log.setLevel('INFO')

        self._host = host_address
        self._user = user
        self._pwd = pwd

        self._downloadData()

    def _downloadData(self):
        self.log.info('Downloading configuration data from Gateway...')
        url = 'http://' + self._host + '/mlgwpservices.json'
        auth = (self._user, self._pwd)
        response = requests.get(url, auth=auth)
        configurationdata = json.loads(response.text)
        self.configureMLGW((configurationdata))

    def configureMLGW(self, data):
        self.log.info('Processing Gateway configuration data...\n')
        const.gateway['Serial_Number'] = data['sn']
        const.gateway['Project'] = data['project']
        const.gateway['Installer'] = str(data['installer']['name'])
        const.gateway['Contact'] = str(data['installer']['contact'])

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
                        source_id = self._srcdictsanitize(const._blgw_srcdict, source_id).upper()
                        device['Sources'][str(source["name"])]['source'] = source_id
                        device['Sources'][str(source["name"])]['uniqueID'] = str(source['sourceId'])
                        source_tuple = (str(source["name"]), source_id)
                        cmd_tuple = (source_id,(int(selectCmd["cmd"]),int(selectCmd["unit"])))
                        device['Sources'][str(source["name"])]['BR1_cmd'] = cmd_tuple
                        if source.has_key('channels'):
                            device['Sources'][str(source["name"])][
                                'channel_track'] = OrderedDict()
                            for channel in source['channels']:
                                c_num = ''
                                num = channel['selectSEQ'][::2]
                                for n in num:
                                    c_num += str(n)
                                device['Sources'][str(source["name"])]['channel_track'][c_num] = OrderedDict()
                                device['Sources'][str(source["name"])]['channel_track'][c_num]['name'] = channel['name']
                                device['Sources'][str(source["name"])]['channel_track'][c_num]['icon'] = channel['icon']

                        if source_tuple not in const.available_sources:
                            const.available_sources.append(source_tuple)

                const.devices.append(device)
            const.rooms.append(room)

        self.log.info('Found ' + str(len(const.devices)) + ' AV Renderers!')
        for i in range(len(const.devices)):
            self.log.info('\tMLN ' + str(const.devices[i].get('MLN')) + ': ' + str(const.devices[i].get('Device')))
        self.log.info('\tFound ' + str(len(const.available_sources)) + ' Available Sources [Name, Type]:')
        for i in range(len(const.available_sources)):
            self.log.info('\t\t' + str(list(const.available_sources[i])))
        self.log.info('Done!\n')

        self.log.debug(json.dumps(const.gateway, indent=4))
        self.log.debug(json.dumps(const.rooms, indent=4))
        self.log.debug(json.dumps(const.devices, indent=4))

    def get_masterlink_id(self, mlgw, mlcli):
        self.log.info("Finding MasterLink ID of products:")
        if mlgw.is_connected and mlcli.is_connected:
            for device in const.devices:
                self.log.info("Finding MasterLink ID of product " + device.get('Device'))
                # Ping the device with a light timeout to elicit a ML telegram containing its ML_ID
                mlgw.send_beo4_cmd(int(device.get('MLN')),
                                   const.CMDS_DEST.get("AUDIO SOURCE"),
                                   const.BEO4_CMDS.get("LIGHT TIMEOUT"))

                if device.get('Serial_num') is None:
                    # If this is a MasterLink product it has no serial number...
                    # loop to until expected response received from ML Command Line Interface
                    while not mlcli.last_message.has_key('to_device') and mlcli.last_message[
                        'from_device'] == "MLGW" and mlcli.last_message[
                        'payload_type'] == "MLGW_REMOTE_BEO4" and mlcli.last_message[
                        'payload']['command'] == "LIGHT TIMEOUT":
                        asyncore.loop(count=1, timeout=0.2)

                    device['ML_ID'] = mlcli.last_message.get('to_device')
                    self.log.info("\tMasterLink ID of product " +
                                 device.get('Device') + " is " + device.get('ML_ID') + ".\n")
                else:
                    # If this is a NetLink product then it has a serial number and no ML_ID
                    device['ML_ID'] = 'NA'
                    self.log.info("\tNetworkLink ID of product " + device.get('Device') + " is " +
                                 device.get('Serial_num') + ". No MasterLink ID assigned.\n")

    def _srcdictsanitize(self, d, s):
        result = d.get(s)
        if result == None:
            result = s
        return str(result)
