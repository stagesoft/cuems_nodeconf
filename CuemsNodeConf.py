import netifaces
import time
import os.path
from os import system
import sys
import subprocess

from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes

import logging

from .CuemsAvahiListener import CuemsAvahiListener
from .CuemsNode import CuemsNode, CuemsNodeDict

from ..ConfigManager import ConfigManager
from ..XmlReaderWriter import XmlReader, XmlWriter

CUEMS_CONF_PATH = '/etc/cuems/'
MAP_SCHEMA_FILE = 'network_map.xsd'
MAP_FILE = 'network_map.xml'
CUEMS_SERVICE_TEMPLATES_PATH = '/usr/share/cuems/'
CUEMS_SERVICE_FILE = 'cuems.service'
CUEMS_MASTER_LOCK_FILE = 'master.lock'

'''
logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )
'''

class CuemsNodeConf():
    def get_ip():
        return netifaces.ifaddresses('ethernet0')[netifaces.AF_INET][0]['addr']

    nodes = CuemsNodeDict()

    def __init__(self, ip=get_ip()):

        self.logger = logging.getLogger('Cuems-NodeConf')

        # Conf load manager
        try:
            self.cm = ConfigManager(path=CUEMS_CONF_PATH, nodeconf=True)
        except FileNotFoundError:
            self.logger.critical(
                'Node config file could not be found. Exiting !!!!!')
            exit(-1)

        self.xsd_path = os.path.join( CUEMS_CONF_PATH, MAP_SCHEMA_FILE)
        self.map_path = os.path.join( CUEMS_CONF_PATH, MAP_FILE)

        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        self.ip = ip
        self.services = ['_cuems_nodeconf._tcp.local.']

        self.start_avahi_listener()
        
        self.node = self.retreive_local_node()

        # Check for first run flag in service file
        if self.node.node_type == CuemsNode.NodeType.firstrun:
            self.logger.debug("First time conf file detected, triying to autoconfigure node")
            self.set_node_type()
        else:
            self.logger.debug(f"Allready configured as {self.node.node_type.name}")
        
        # If I am master finally wait a bit for slaves to appear on the net
        if self.node.node_type == CuemsNode.NodeType.master:
            time.sleep(self.cm.node_conf['nodeconf_timeout'] / 1000)
            
            # publish avahi alias as master.local
            self.publish_master_alias()

        if self.listener.nodes.firstruns:
            self.logger.debug('Waiting for some other "first-run" nodes')
        while self.listener.nodes.firstruns:
            time.sleep(0.5)

        self.check_nodes()

        try:
            self.write_network_map()
        except Exception as e:
            self.logger.exception(e)

        self.update_master_lock_file(os.path.join( CUEMS_CONF_PATH, CUEMS_MASTER_LOCK_FILE))

        if self.node.node_type == CuemsNode.NodeType.master:
            sys.exit(100)
        elif self.node.node_type == CuemsNode.NodeType.slave:
            sys.exit(101)

    def start_avahi_listener(self):
        # self.listener = CuemsAvahiListener(callback=self.callback)
        self.listener = CuemsAvahiListener()
        self.browser = ServiceBrowser(
            self.zeroconf, self.services, self.listener)
        time.sleep(2)

    def set_node_type(self):
        if not self.listener.nodes.masters:
            self.logger.debug('No master node on the network, I become MASTER!')
            self.node.node_type = CuemsNode.NodeType.master

            # Copy master node service template
            source = os.path.join(CUEMS_SERVICE_TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.master'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)
            command = f'sudo cp {source} {target}'
            os.system(command)
        else:
            self.logger.debug('Master present on the in network WE STAY SLAVE')
            self.node.node_type = CuemsNode.NodeType.slave

            # Copy slave node service template
            source = os.path.join(CUEMS_SERVICE_TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.slave'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)
            os.system(f'sudo cp {source} {target}')
        
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
            self.network_map[node.mac] = node
        
        print("---")
        print("Nodes read from existing XML network map:")
        for item, value in self.network_map.items():
            print(value)
        print("---")

    def cleanup(self):
        try:
            os.remove(os.path.join(CUEMS_CONF_PATH, self.cm.show_lock_file))
        except FileNotFoundError:
            pass

    def callback(self, caller_node=None, action=CuemsAvahiListener.Action.ADD):
        self.logger.debug(f" {action} callback!!!, Node: {caller_node} ")

        self.check_nodes()

    def check_nodes(self):
        # self.logger.debug(self.listener.nodes)
        if self.listener.nodes.masters:
            self.logger.debug(f"Master node(s):\n{self.listener.nodes.masters}")
        else:
            self.logger.debug(f"We have no MASTER!! yet? waiting for it")
        if self.listener.nodes.slaves:
            self.logger.debug(
                f"We have {len(self.listener.nodes.slaves)} slaves")
            self.logger.debug(f"Slave node(s):\n{self.listener.nodes.slaves}")
        else:
            self.logger.debug("we have no slaves")

    def check_first_run(self):
        for node in self.listener.nodes.firstruns:
            if node.ip == self.ip:
                return True

        return False
    
    def retreive_local_node(self):
        retries = 0
        sleep_time = 1.5
        
        while retries < 6:
            for node in self.listener.nodes.values():
                if node.ip == self.ip:
                    found = True
                    return node

            time.sleep(sleep_time)
            sleep_time = sleep_time * 2
            self.logger.debug("waiting for local node to appear on the network")
            retries += 1
        
        raise Exception('Local node avahi service not detected')

    def publish_master_alias(self):
        #avahi-publish -a -f -R master.local 192.168.1.12
        try:
            subprocess.Popen(["avahi-publish", "-aR", "master.local", self.ip], close_fds=True)
            self.logger.debug(f"Publishing master.local alias in  {self.ip}")
        except Exception as e:
            self.logger.debug(f"error publishing alias, {type(e)}. {e}")

    def update_master_lock_file(self, path):
        if self.node.node_type == CuemsNode.NodeType.master:
            print("master")
            if  not os.path.isfile(path):
                print("not file")
                try:
                    with open(path, 'a') as results_file:
                        results_file.write('\n')
                except:
                    self.logger.warning("could not write master lock file")
        else:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    self.logger.warning("could not delete master lock file")

            


