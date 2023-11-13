try:
    import indigo
except ImportError:
    pass
import asyncore
import json
import requests
import logging
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from collections import OrderedDict

import Resources.CONSTANTS as CONST


class MLConfig:

    def __init__(self, host_address='blgw.local', user='admin', pwd='admin', debug=False):
        self.debug = debug

        self._host = host_address
        self._user = user
        self._pwd = pwd

        self._download_data()

    def _download_data(self):
        try:
            indigo.debugger()

            indigo.server.log('Downloading configuration data from Gateway...', level=logging.WARNING)
            url = 'http://' + str(self._host) + '/mlgwpservices.json'
            # try Basic Auth next (this is needed for the BLGW)
            response = requests.get(url, auth=HTTPBasicAuth(self._user, self._pwd))

            if response.status_code == 401:
                # try Digest Auth first (this is needed for the MLGW)
                response = requests.get(url, auth=HTTPDigestAuth(self._user, self._pwd))

            if response.status_code == 401:
                return
            else:
                # Once logged in successfully download and process the configuration data
                configurationdata = json.loads(response.text)
                self.configure_mlgw(configurationdata)
        except ValueError:
            pass

    def configure_mlgw(self, data):
        if "BeoGateway" not in indigo.devices.folders:
            indigo.devices.folder.create("BeoGateway")
        folder_id = indigo.devices.folders.getId("BeoGateway")

        # Check to see if any devices already exist to avoid duplication
        _nodes = []
        for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
            _nodes.append(int(node.address))

        indigo.server.log('Processing Gateway configuration data...\n', level=logging.WARNING)
        # Check to see if gateway device exists and create one if not
        try:
            gw = indigo.device.create(
                protocol=indigo.kProtocol.Plugin,
                name="Bang and Olufsen Gateway",
                description="Automatically generated device for BeoGateway plugin:\n"
                            " - Please do not delete or rename!\n"
                            " - Editing device properties for advanced users only!",
                deviceTypeId="BOGateway",
                pluginId='uk.co.lukes_plugins.BeoGateway.plugin',
                folder=folder_id,
                address=1
            )
        except ValueError:
            gw = indigo.devices['Bang and Olufsen Gateway']

        try:
            gateway_type = 'blgw'
            gw.replacePluginPropsOnServer(
                {
                    'serial_no': data['sn'],
                    'project': data['project'],
                    'installer': str(data['installer']['name']),
                    'contact': str(data['installer']['contact']),
                    'isBLGW': 'BLGW'
                }
            )
        except KeyError:
            gateway_type = 'mlgw'
            gw.replacePluginPropsOnServer(
                {
                    'serial_no': data['sn'],
                    'project': data['project'],
                    'isBLGW': 'MLGW'
                }
            )

        # Replace States
        gw.updateStatesOnServer(CONST.gw_all_stb)

        # Loop over the config data to find the rooms, devices and sources in the installation
        for zone in data["zones"]:
            # Get rooms
            if int(zone['number']) == 240:
                continue
            room = OrderedDict()
            room['Room_Number'] = zone['number']
            if gateway_type == 'blgw':
                # BLGW arranges rooms within zones
                room['Zone'] = str(zone['name']).split('/')[0]
                room['Room_Name'] = str(zone['name']).split('/')[1]
            elif gateway_type == 'mlgw':
                # MLGW has no zoning concept - devices are arranged in rooms only
                room['Zone'] = 'NA'
                room['Room_Name'] = str(zone['name'])

            # Get products
            for product in zone["products"]:
                device = OrderedDict()

                # Device identification
                device['Device'] = str(product["name"])
                device['MLN'] = product["MLN"]
                device['ML_ID'] = ''
                try:
                    device['Serial_num'] = str(product["sn"])
                except KeyError:
                    device['Serial_num'] = 'NA'
                    
                # Physical location
                if gateway_type == 'blgw':
                    # BLGW arranges rooms within zones
                    device['Zone'] = str(zone['name']).split('/')[0]
                    device['Room'] = str(zone['name']).split('/')[1]
                elif gateway_type == 'mlgw':
                    # MLGW has no zoning concept - devices are arranged in rooms only
                    device['Room'] = str(zone['name'])
                device['Room_Number'] = str(zone["number"])

                # Source information
                device['Sources'] = dict()

                for source in product["sources"]:
                    src_name = str(source["name"]).strip().replace(' ', '_')
                    device['Sources'][src_name] = dict()
                    for selectCmd in source["selectCmds"]:
                        if gateway_type == 'blgw':
                            # get source information from the BLGW config file
                            if str(source['sourceId']) == '':
                                source_id = self._srcdictsanitize(CONST.beo4_commanddict, source['selectID']).upper()
                            else:
                                source_id = str(source['sourceId'].split(':')[0])
                                source_id = self._srcdictsanitize(CONST.blgw_srcdict, source_id).upper()
                            device['Sources'][src_name]['source'] = source_id
                            device['Sources'][src_name]['uniqueID'] = str(source['sourceId'])
                        else:
                            # MLGW config file is structured differently
                            source_id = self._srcdictsanitize(CONST.beo4_commanddict, source['selectID']).upper()
                            device['Sources'][src_name]['source'] = source_id
                        source_tuple = (str(source_id), str(source["name"]))
                        device['Sources'][src_name]['BR1_cmd'] = \
                            dict([('command', int(selectCmd["cmd"])), ('unit', int(selectCmd["unit"]))])

                        # Establish the channel list for sources with favourites lists
                        if 'channels' in source:
                            device['Sources'][src_name]['channels'] = []
                            for channel in source['channels']:
                                c_num = 'c'
                                if gateway_type == 'blgw':
                                    num = channel['selectSEQ'][::2]
                                else:
                                    num = channel['selectSEQ'][:-1]
                                for n in num:
                                    c_num += str(n)
                                c = (c_num, str(channel['name']))
                                device['Sources'][src_name]['channels'].append(c)

                        if source_tuple not in CONST.available_sources:
                            CONST.available_sources.append(source_tuple)

                # Create indigo devices to represent the B&O AV renderers in the installation
                if int(device['MLN']) not in _nodes:
                    if self.debug:
                        indigo.server.log("New Device! Creating Indigo Device " + device['Device'],
                                          level=logging.DEBUG)
                    
                    node = indigo.device.create(
                        protocol=indigo.kProtocol.Plugin,
                        name=device['Device'],
                        description="Automatically generated device for BeoGateway plugin:\n"
                                    "- Device data sourced from gateway config:\n"
                                    "- Please do not delete or rename!\n"
                                    "- Editing device properties for advanced users only!",
                        deviceTypeId="AVrenderer",
                        pluginId='uk.co.lukes_plugins.BeoGateway.plugin',
                        folder=folder_id,
                        address=device['MLN'],
                        props={
                            'serial_no': device['Serial_num'],
                            'mlid': 'NA',
                            'zone': room['Zone'],
                            'room': device['Room'],
                            'roomnum': device['Room_Number'],
                            'sources': device['Sources']
                        }
                    )

                    # Update the device states
                    node.updateStatesOnServer(CONST.standby_state)
                    node.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                else:
                    # if node already exists, update the properties in case they have been updated
                    for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
                        if int(node.address) == int(device['MLN']):
                            if self.debug:
                                indigo.server.log("Old Device! Updating Properties for " + device['Device'] + "\n",
                                                  level=logging.DEBUG)
                            # Update the name of the device
                            node.name = device['Device']
                            node.description = "Automatically generated device for BeoGateway plugin:\n" \
                                               " - Device data sourced from gateway config:\n" \
                                               " - Please do not delete or rename!\n" \
                                               " - Editing device properties for advanced users only!"
                            node.replaceOnServer()
                            # Update the properties of the device
                            node_props = node.pluginProps
                            node_props.update(
                                {
                                    'serial_no': device['Serial_num'],
                                    'zone': room['Zone'],
                                    'room': device['Room'],
                                    'roomnum': device['Room_Number'],
                                    'sources': device['Sources']
                                }
                            )
                            node.replacePluginPropsOnServer(node_props)

                            # Update the device states
                            node.stateListOrDisplayStateIdChanged()
                            node.updateStatesOnServer(CONST.standby_state)
                            node.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                            indigo.device.moveToFolder(node.id, value=folder_id)
                            break

            # Keep track of the room data
            CONST.rooms.append(room)

        # Report details of the configuration
        n_devices = indigo.devices.len(filter="uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer")
        indigo.server.log('Found ' + str(n_devices) + ' AV Renderers!', level=logging.DEBUG)
        for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
            indigo.server.log('\tMLN ' + str(node.address) + ': ' + str(node.name), level=logging.INFO)
        indigo.server.log('\tFound ' + str(len(CONST.available_sources)) + ' Available Sources [Type, Name]:',
                          level=logging.DEBUG)
        for i in range(len(CONST.available_sources)):
            indigo.server.log('\t\t' + str(list(CONST.available_sources[i])), level=logging.INFO)
        indigo.server.log('\tDone!\n', level=logging.DEBUG)

    @staticmethod
    def get_masterlink_id(mlgw, mlcli):
        # Identify the MasterLink ID of products
        indigo.server.log("Finding MasterLink ID of products:", level=logging.WARNING)
        if mlgw.is_connected and mlcli.is_connected:
            for node in indigo.devices.iter('uk.co.lukes_plugins.BeoGateway.plugin.AVrenderer'):
                indigo.server.log("Finding MasterLink ID of product " + node.name, level=logging.WARNING)
                # Ping the device with a light timeout to elicit a ML telegram containing its ML_ID
                mlgw.send_beo4_cmd(int(node.address),
                                   CONST.CMDS_DEST.get("AUDIO SOURCE"),
                                   CONST.BEO4_CMDS.get("LIGHT TIMEOUT"))
                node_props = node.pluginProps
                if node_props['serial_no'] in [None, 'NA', '']:
                    # If this is a MasterLink product it has no serial number...
                    # loop to until expected response received from ML Command Line Interface
                    test = True
                    while test:
                        try:
                            if mlcli.last_message['from_device'] == "MLGW" and \
                                mlcli.last_message['payload_type'] == "MLGW_REMOTE_BEO4" and \
                                    mlcli.last_message['State_Update']['command'] == "Light Timeout":

                                if node_props['mlid'] == 'NA':
                                    node_props['mlid'] = mlcli.last_message.get('to_device')
                                    node_props['serial_no'] = 'NA'
                                    node.replacePluginPropsOnServer(node_props)

                                indigo.server.log("\tMasterLink ID of product " +
                                                  node.name + " is " + node_props['mlid'] + ".\n",
                                                  level=logging.DEBUG)
                                test = False
                        except KeyError:
                            asyncore.loop(count=1, timeout=0.2)
                else:
                    # If this is a NetLink product then it has a serial number and no ML_ID
                    indigo.server.log("\tNetworkLink ID of product " + node.name + " is " +
                                      node_props['serial_no'] + ". No MasterLink ID assigned.\n",
                                      level=logging.DEBUG)

    # ########################################################################################
    # Utility Functions
    @staticmethod
    def _srcdictsanitize(d, s):
        result = d.get(s)
        if result is None:
            result = s
        return str(result)
