import netifaces
import time
import os.path
from os import system
import sys
import subprocess
import systemd.daemon
import dbus
import shutil

from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes

import logging


from CuemsAvahiListener import CuemsAvahiListener
from CuemsNode import CuemsNode, CuemsNodeDict

from cuemsutils.xml.XmlReaderWriter import XmlReader, XmlWriter

CUEMS_CONF_PATH = '/etc/cuems/'
MAP_SCHEMA_FILE = 'network_map.xsd'
MAP_FILE = 'network_map.xml'
CUEMS_SERVICE_TEMPLATES_PATH = '/usr/share/cuems/'
CUEMS_SERVICE_FILE = 'cuems.service'
CUEMS_MASTER_LOCK_FILE = 'master.lock'
MASTER_INTERFACE_FILE = 'interfaces.master'

MASTER_ALIAS='controller.local'
CONTROLLER_ALIAS='formitgo.local'

'''
logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )
'''

class CuemsNodeConf():

    nodes = CuemsNodeDict()

    def __init__(self):

        self.logger = logging.getLogger('Cuems-NodeConf')

        # Conf load manager
        # disable temporally until we got nodeconf again
        # try:
        #     self.cm = ConfigManager(path=CUEMS_CONF_PATH, nodeconf=True)
        # except FileNotFoundError:
        #     self.logger.critical(
        #         'Node config file could not be found. Exiting !!!!!')
          
        #     exit(-1)

        self.xsd_path = os.path.join( CUEMS_CONF_PATH, MAP_SCHEMA_FILE)
        self.map_path = os.path.join( CUEMS_CONF_PATH, MAP_FILE)
        
        self.get_ips()
        self.zeroconf = Zeroconf(interfaces=[self.ip],ip_version=IPVersion.V4Only)

        
        

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
            #time.sleep(self.cm.node_conf['nodeconf_timeout'] / 1000)
            #temp until we got nodeconf again
            time.sleep(5)
            
            # publish avahi alias as in internal interface 0
            self.publish_master_alias()

            # publish wifi alias as in wifi interface
            if self.controller_ip:
                self.publish_controller_alias()

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
        # Check if I am the master node


        # if self.node.node_type == CuemsNode.NodeType.master:
        #     sys.exit(100)
        # elif self.node.node_type == CuemsNode.NodeType.slave:
        #     sys.exit(101)

        self.logger.debug('Startup complete, notifying systemd')
        systemd.daemon.notify('READY=1')

         #TODO: add timeout for the waiting loops
    def get_ips(self):
        self.ip = None
        self.controller_ip = None
        while True:
            try:
                self.ip = netifaces.ifaddresses('bridge0:avahi')[netifaces.AF_INET][0]['addr']
                self_controller_ip = None
                logging.debug(f"Found bridge0:avahi interface, IP: {self.ip}")
                return 
            except (ValueError, KeyError):
                logging.debug("bridge0:avahi interface not found, triying next ones")
                try:
                    self.ip = netifaces.ifaddresses('ethernet1:avahi')[netifaces.AF_INET][0]['addr']
                    logging.debug(f"Found ethernet1:avahi interface, IP: {self.ip}")
                except (ValueError, KeyError):
                    logging.debug("Waiting for ethernet1:avahi interface to appear")
    
                try:
                    self.controller_ip = netifaces.ifaddresses('bond0')[netifaces.AF_INET][0]['addr']
                    if self.ip != None:
                        logging.debug(f"Found bond0 interface, CONTROLLER IP: {self.controller_ip}")
                        return
                    else:
                        logging.debug(f"Found bond0 interface, but we are mising ethernet1:avahi interface, continuing")
                except (ValueError, KeyError):
                    logging.debug("Waiting for bond0 interface to appear")
            time.sleep(1)

    def start_avahi_listener(self):
        # self.listener = CuemsAvahiListener(callback=self.callback)
        self.listener = CuemsAvahiListener(ip=self.ip)
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

            shutil.copy2(source, target)
            self.change_network_settings_to_master()
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

        writer = XmlWriter(schema_name = self.xsd_path, xmlfile = self.map_path, xml_root_tag='CuemsNetworkMap')
        writer.write_from_object(map)
        self.logger.debug("Network map written to XML")


    def read_network_map(self):
        reader = XmlReader(schema_name = self.xsd_path, xmlfile = self.map_path)
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
        try:
            subprocess.Popen(["avahi-publish", "-aR", MASTER_ALIAS, self.ip], close_fds=True)
            self.logger.debug(f"Publishing {MASTER_ALIAS} alias in  {self.ip}")
        except Exception as e:
            self.logger.debug(f"error publishing alias, {type(e)}. {e}")

    def publish_controller_alias(self):
        try:
            subprocess.Popen(["avahi-publish", "-aR", CONTROLLER_ALIAS, self.controller_ip], close_fds=True)
            self.logger.debug(f"Publishing {CONTROLLER_ALIAS} alias in  {self.controller_ip}")
        except Exception as e:
            self.logger.debug(f"error publishing alias, {type(e)}. {e}")

    def update_master_lock_file(self, path):
        if self.node.node_type == CuemsNode.NodeType.master:
            if  not os.path.isfile(path):
                try:
                    with open(path, 'a') as results_file:
                        results_file.write('\n')
                    self.logger.debug("Created new master file")
                except:
                    self.logger.warning("could not write master lock file")
        else:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    self.logger.debug("Removed master file")
                except OSError:
                    self.logger.warning("could not delete master lock file")
    
    def restart_network_service(self):
        try:
            sysbus = dbus.SystemBus()
            systemd1 = sysbus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
            manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
            
            job = manager.StopUnit('networking.service', 'fail')
            self.logger.debug("Stopping networking service")
            time.sleep(10)
            job = manager.StartUnit('networking.service', 'fail')
            self.logger.debug("Starting networking service")
            time.sleep(10)
            self.logger.debug("Networking service restarted successfully, continuing")

            return True

        except Exception as e:
            self.logger.error(f"Error restarting networking service: {e}")
            return False
        
    def change_network_settings_to_master(self):
        try:
            source = os.path.join(CUEMS_SERVICE_TEMPLATES_PATH, MASTER_INTERFACE_FILE)
            target = '/etc/network/interfaces'
            shutil.copy2(source, target)
        except Exception as e:
            self.logger.error(f"Error copying interfaces file: {e}")
        
        return self.restart_network_service()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(name)s: %(message)s',
                        )
    CuemsNodeConf()