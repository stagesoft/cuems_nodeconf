import socket
import netifaces
import threading
import time
import os.path


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
NODE_FILE = 'node'

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
        self.node_type_path = os.path.join( CUEMS_CONF_PATH, NODE_FILE)
        self.autoconf_lock_file_path = os.path.join( CUEMS_CONF_PATH, self.cm.autoconf_lock_file )

        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        self.settings_dict = settings_dict
        self.services = [self.settings_dict['type_']]

        self.node = CuemsNode()

        # if autoconf file exists mark first time conf
        self.first_time = os.path.isfile(self.autoconf_lock_file_path)
 

        self.start_avahi_listener()

        

        if self.first_time:
            self.logger.debug("First time conf file detected, triying to autoconfigure node")
            self.set_node_type()
            self.register_node()
            self.write_network_map()
            self.autoconf_finished()
        else:
            self.logger.debug("Allready configured, reading conf")
            self.read_node_type()
            self.register_node()
            
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

    def read_node_type(self):
        try:
            with open(self.node_type_path, 'r') as file:
                self.node.node_type = CuemsNode.NodeType[file.read().rstrip('\r\n')]
            self.logger.debug(f"We are {self.node.node_type.name.upper()} from conf")
        except FileNotFoundError:
            self.logger.debug("can not read node type file")

    def set_node_type(self):
        self.master_exists = self.find_master()

        if not self.master_exists:
            self.logger.debug('No Master in network, WE ARE MASTER')
            self.node.node_type = CuemsNode.NodeType.master
        else:
            self.node.node_type = CuemsNode.NodeType.slave
            self.logger.debug('Master present in network WE STAY SLAVE')
        
        try:
            with open(self.node_type_path, 'w') as file:
                file.write(self.node.node_type.name)
        except FileNotFoundError:
            self.logger.debug("can not write node type file")


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
        


        self.write_network_map(self.network_map)
        print(f' new network map: {self.network_map}')


    def cleanup(self):
        try:
            os.remove(os.path.join(CUEMS_CONF_PATH,
                                   self.cm.autoconf_lock_file))
        except FileNotFoundError:
            pass

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

    def find_master(self):
        for node in self.listener.nodes.values():
            self.logger.debug(node)
            if CuemsNode.NodeType.master in node.values():
                return True
        return False

    def check_nodes(self):
        self.logger.debug(self.listener.nodes)
        if self.listener.nodes.master:
            self.logger.debug(f"master: {self.listener.nodes.master}")
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

    def autoconf_finished(self):
        self.logger.debug("autoconf finished, deleting first_time.lock")
        try:
            os.remove(self.autoconf_lock_file_path)
        except FileNotFoundError as e:
            self.logger.critical("first_time.lock not found, something is wrong")
            raise e

    def shutdown(self):
        self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()
