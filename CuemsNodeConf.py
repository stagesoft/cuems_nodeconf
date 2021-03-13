import socket
import netifaces
import threading
import time
import os.path
from os import system

from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes

import logging


from .CuemsConfServer import CuemsConfServer
from .CuemsAvahiListener import CuemsAvahiListener
from .CuemsNode import CuemsNode, CuemsNodeDict

from .CuemsSettings import read_conf

from ..ConfigManager import ConfigManager
from ..XmlReaderWriter import XmlReader, XmlWriter

CUEMS_CONF_PATH = '/etc/cuems/'
MAP_SCHEMA_FILE = 'network_map.xsd'
MAP_FILE = 'network_map.xml'
CUEMS_SERVICE_TEMPLATES_PATH = '/usr/share/cuems/'
CUEMS_SERVICE_FILE = 'cuems.service'

logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )


class CuemsNodeConf():
    nodes = CuemsNodeDict()

    def __init__(self, settings_dict=read_conf()):

        self.logger = logging.getLogger('Cuems-NodeConf')
        self.init_done = False

        # Conf load manager
        try:
            self.cm = ConfigManager(path=CUEMS_CONF_PATH)
        except FileNotFoundError:
            self.logger.critical(
                'Node config file could not be found. Exiting !!!!!')
            exit(-1)

        self.xsd_path = os.path.join( CUEMS_CONF_PATH, MAP_SCHEMA_FILE)
        self.map_path = os.path.join( CUEMS_CONF_PATH, MAP_FILE)

        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        self.settings_dict = settings_dict
        self.services = [self.settings_dict['type_']]

        self.start_avahi_listener()
        
        # self.node = CuemsNode()
        self.node = self.retreive_local_node()

        if self.node.node_type == CuemsNode.NodeType.firstrun:
            self.logger.debug("First time conf file detected, triying to autoconfigure node")
            self.set_node_type()

            self.write_network_map()
        else:
            self.logger.debug("Allready configured, reading conf")
            
            if self.node.node_type is CuemsNode.NodeType.master:
                self.read_network_map()
                self.check_network_map()
        
        

        # time.sleep(2)
        self.check_nodes()

        self.init_done = True

    def start_avahi_listener(self):
        self.listener = CuemsAvahiListener(callback=self.callback)
        self.browser = ServiceBrowser(
            self.zeroconf, self.services, self.listener)
        time.sleep(2)

    def set_node_type(self):
        if not self.listener.nodes.masters:
            self.logger.debug('No Master in network, WE ARE MASTER')
            self.node.node_type = CuemsNode.NodeType.master

            # Copy master node service template
            source = os.path.join(CUEMS_SERVICE_TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.master'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)
            command = f'cp {source} {target}'
            os.system(command)
            
        else:
            self.node.node_type = CuemsNode.NodeType.slave
            self.logger.debug('Master present in network WE STAY SLAVE')

            # Copy slave node service template
            source = os.path.join(CUEMS_CONF_PATH, CUEMS_SERVICE_FILE) + '.slave'
            target = os.path.join(CUEMS_SERVICE_TEMPLATES_PATH, CUEMS_SERVICE_FILE)
            os.system(f'cp {source} {target}')
        
    def write_network_map(self, map=None):
        if not map:
            map = self.listener.nodes

        writer = XmlWriter(schema = self.xsd_path, xmlfile = self.map_path, xml_root_tag='CuemsNetworkMap')
        writer.write_from_object(map)


    def read_network_map(self):
        reader = XmlReader(schema = self.xsd_path, xmlfile = self.map_path)
        self.network_map = CuemsNodeDict()
        nodes = reader.read_to_objects()
        for node in nodes:
            self.network_map[node.uuid] = node
        
        for item, value in self.network_map.items():
            print("---")
            print("nodes from xml:")
            print(value)
        print("---")

    def check_network_map(self):
        '''
        for uuid, node in self.listener.nodes.items():
            if uuid in self.network_map:
                self.network_map[uuid].present = True
            else:
                print(f'node {uuid} is new, adding')
                self.network_map[uuid] = node
        keys_to_delete = list()

        for uuid, node in self.network_map.items():
            if uuid not in self.listener.nodes:
                print(f'node {uuid} is missing!')
                keys_to_delete.append(uuid)
                     
        if keys_to_delete:
            for key in keys_to_delete:
                del self.network_map[key]
        '''
        
        self.write_network_map(self.network_map)
        print(f' New network map: {self.network_map}')


    def cleanup(self):
        try:
            os.remove(os.path.join(CUEMS_CONF_PATH, self.cm.show_lock_file))
        except FileNotFoundError:
            pass

    def callback(self, caller_node=None, action=CuemsAvahiListener.Action.ADD):
        self.logger.debug(f" {action} callback!!!, Node: {caller_node} ")
        if not self.init_done:
            self.logger.debug("INIT NOT DONE")
            return None

        self.check_nodes()

    def check_nodes(self):
        self.logger.debug(self.listener.nodes)
        if self.listener.nodes.masters:
            self.logger.debug(f"master: {self.listener.nodes.masters}")
        else:
            raise Exception("we have no master!!")
        if self.listener.nodes.slaves:
            self.logger.debug(
                f"we have {len(self.listener.nodes.slaves)} slaves")
            self.logger.debug(f"slaves: {self.listener.nodes.slaves}")
        else:
            self.logger.debug("we have no slaves")

    def register_node(self):

        self.service_info = ServiceInfo(
            self.settings_dict['type_'],
            self.settings_dict['name'],
            addresses=[self.settings_dict['ip']],
            port=self.settings_dict['port'],
            properties={'node_type': self.node.node_type.name},
            server=self.settings_dict['server'],
            host_ttl=self.settings_dict['host_ttl'],
            other_ttl=self.settings_dict['other_ttl'],

        )
        self.logger.debug(f"registering node as {self.node.node_type.name.upper()}")
        self.zeroconf.register_service(self.service_info)
        self.logger.debug("Node registered")

    def check_first_run(self):
        for node in self.listener.nodes.firstruns:
            if node.ip == self.settings_dict['ip']:
                return True

        return False
    
    def retreive_local_node(self):
        for node in self.listener.nodes.values():
            if node.ip == self.settings_dict['ip']:
                return node
        
        raise Exception('Local node avahi service not detected')

    def shutdown(self):
        self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()
