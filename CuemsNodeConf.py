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



from CuemsAvahiListener import CuemsAvahiListener
from CuemsNode import CuemsNode, CuemsNodeDict

from cuemsutils.xml.XmlReaderWriter import XmlReader, XmlWriter
from cuemsutils.timeoutloop import Timeoutloop
from cuemsutils.log import Logger, logged

CUEMS_CONF_PATH = '/etc/cuems/'
MAP_SCHEMA_FILE = 'network_map.xsd'
MAP_FILE = 'network_map.xml'
TEMPLATES_PATH = '/usr/share/cuems/'
CUEMS_SERVICE_FILE = 'cuems.service'
CUEMS_MASTER_LOCK_FILE = 'master.lock'
CONTROLLER_INTERFACES_TEMPLATE = 'interfaces.master'
NODE_INTERFACES_TEMPLATE = 'interfaces.node'

MASTER_ALIAS='controller.local'
CONTROLLER_ALIAS='formitgo.local'

'''
Logger.basicConfig(level=Logger.DEBUG,
                    format='%(name)s: %(message)s',
                    )
'''

class CuemsNodeConf():

    nodes = CuemsNodeDict()

    def __init__(self):


        # Conf load manager
        # disable temporally until we got nodeconf again
        # try:
        #     self.cm = ConfigManager(path=CUEMS_CONF_PATH, nodeconf=True)
        # except FileNotFoundError:
        #     Logger.critical(
        #         'Node config file could not be found. Exiting !!!!!')
          
        #     exit(-1)

        self.xsd_path = os.path.join( CUEMS_CONF_PATH, MAP_SCHEMA_FILE)
        self.map_path = os.path.join( CUEMS_CONF_PATH, MAP_FILE)

        self.services = ['_cuems_nodeconf._tcp.local.']
        

         #TODO: add timeout for the waiting loops
    def stop():
        pass
        exit(-1)

    def start(self):
        Logger.debug('Starting CuemsNodeConf')
        self.run()
    def run(self):
        Logger.debug('Running CuemsNodeConf')
        try:
            self.get_ips()
        except TimeoutError:
            Logger.error('Could not find network interfaces')

        self.zeroconf = Zeroconf(interfaces=[self.ip],ip_version=IPVersion.V4Only)

        self.start_avahi_listener()
        
        try:
            self.node = self.retreive_local_node()
        except TimeoutError:
            Logger.critical('Could not find local node on the network')
            sys.exit(-1)

        # Check for first run flag in service file
        if self.node.node_type == CuemsNode.NodeType.firstrun:
            Logger.debug("First time conf file detected, triying to autoconfigure node")
            self.set_node_type()
        else:
            Logger.debug(f"Allready configured as {self.node.node_type.name}")
        
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
            Logger.debug('Waiting for some other "first-run" nodes')
        while self.listener.nodes.firstruns:
            time.sleep(0.5)

        self.check_nodes()

        try:
            self.write_network_map()
        except Exception as e:
            Logger.exception(e)

        self.update_master_lock_file(os.path.join( CUEMS_CONF_PATH, CUEMS_MASTER_LOCK_FILE))
        # Check if I am the master node


        # if self.node.node_type == CuemsNode.NodeType.master:
        #     sys.exit(100)
        # elif self.node.node_type == CuemsNode.NodeType.slave:
        #     sys.exit(101)
        # else:
        self.notify_systemd()
        
    def notify_systemd(self, status='READY=1'):

        Logger.debug('Startup complete, notifying systemd')
        systemd.daemon.notify(status)
    def get_ips(self):
        self.ip = None
        self.controller_ip = None
        for passed in Timeoutloop(timeout=10, interval=1):
            try:
                self.ip = netifaces.ifaddresses('bridge0:avahi')[netifaces.AF_INET][0]['addr']
                self_controller_ip = None
                Logger.debug(f"Found bridge0:avahi interface, IP: {self.ip}")
                return 
            except (ValueError, KeyError):
                Logger.debug("bridge0:avahi interface not found, triying next ones")
                try:
                    self.ip = netifaces.ifaddresses('ethernet1:avahi')[netifaces.AF_INET][0]['addr']
                    Logger.debug(f"Found ethernet1:avahi interface, IP: {self.ip}")
                except (ValueError, KeyError):
                    Logger.debug("Waiting for ethernet1:avahi interface to appear")
    
                try:
                    self.controller_ip = netifaces.ifaddresses('bond0')[netifaces.AF_INET][0]['addr']
                    if self.ip != None:
                        Logger.debug(f"Found bond0 interface, CONTROLLER IP: {self.controller_ip}")
                        return
                    else:
                        Logger.debug(f"Found bond0 interface, but we are mising ethernet1:avahi interface, continuing")
                except (ValueError, KeyError):
                    Logger.debug("Waiting for bond0 interface to appear")

    def start_avahi_listener(self):
        # self.listener = CuemsAvahiListener(callback=self.callback)
        self.listener = CuemsAvahiListener(ip=self.ip)
        self.browser = ServiceBrowser(
            self.zeroconf, self.services, self.listener)
        time.sleep(2)

    def set_node_type(self):
        if not self.listener.nodes.masters:
            Logger.debug('No master node on the network, I become MASTER!')
            self.node.node_type = CuemsNode.NodeType.master

            # Copy master node service template
            source = os.path.join(TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.master'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)

            shutil.copy2(source, target)
            self.change_network_to_master()
            self.get_ips()
        else:
            Logger.debug('Master present on the in network WE STAY SLAVE')
            self.node.node_type = CuemsNode.NodeType.slave

            # Copy slave node service template
            source = os.path.join(TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.slave'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)
            os.system(f'sudo cp {source} {target}')
        
    def write_network_map(self, map=None):
        if not map:
            map = self.listener.nodes

        writer = XmlWriter(schema_name = self.xsd_path, xmlfile = self.map_path, xml_root_tag='CuemsNetworkMap')
        writer.write_from_object(map)
        Logger.debug("Network map written to XML")


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
        Logger.debug(f" {action} callback!!!, Node: {caller_node} ")

        self.check_nodes()

    def check_nodes(self):
        # Logger.debug(self.listener.nodes)
        if self.listener.nodes.masters:
            Logger.debug(f"Master node(s):\n{self.listener.nodes.masters}")
        else:
            Logger.debug(f"We have no MASTER!! yet? waiting for it")
        if self.listener.nodes.slaves:
            Logger.debug(
                f"We have {len(self.listener.nodes.slaves)} slaves")
            Logger.debug(f"Slave node(s):\n{self.listener.nodes.slaves}")
        else:
            Logger.debug("we have no slaves")

    def check_first_run(self):
        for node in self.listener.nodes.firstruns:
            if node.ip == self.ip:
                return True

        return False
    
    def retreive_local_node(self):
        retries = 0
        sleep_time = 1.5
        for passed in Timeoutloop(timeout=10, interval=1):
            for node in self.listener.nodes.values():
                if node.ip == self.ip:
                    found = True
                    return node

            Logger.debug("waiting for local node to appear on the network")
        

    def publish_master_alias(self):
        try:
            subprocess.Popen(["avahi-publish", "-aR", MASTER_ALIAS, self.ip], close_fds=True)
            Logger.debug(f"Publishing {MASTER_ALIAS} alias in  {self.ip}")
        except Exception as e:
            Logger.debug(f"error publishing alias, {type(e)}. {e}")

    def publish_controller_alias(self):
        try:
            subprocess.Popen(["avahi-publish", "-aR", CONTROLLER_ALIAS, self.controller_ip], close_fds=True)
            Logger.debug(f"Publishing {CONTROLLER_ALIAS} alias in  {self.controller_ip}")
        except Exception as e:
            Logger.debug(f"error publishing alias, {type(e)}. {e}")

    def update_master_lock_file(self, path):
        if self.node.node_type == CuemsNode.NodeType.master:
            if  not os.path.isfile(path):
                try:
                    with open(path, 'a') as results_file:
                        results_file.write('\n')
                    Logger.debug("Created new master file")
                except:
                    Logger.warning("could not write master lock file")
        else:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                    Logger.debug("Removed master file")
                except OSError:
                    Logger.warning("could not delete master lock file")
    
    def change_network_to_master(self):
        try:
            sysbus = dbus.SystemBus()
            systemd1 = sysbus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
            manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
            
            job = manager.StopUnit('networking.service', 'fail')
            Logger.debug("Stopping networking service")
            time.sleep(10)
            self.change_network_settings_to_master()
            job = manager.StartUnit('networking.service', 'fail')
            Logger.debug("Starting networking service")
            time.sleep(10)
            Logger.debug("Networking service restarted successfully")
            job = manager.StartUnit('avahi-daemon.service', 'fail')
            time.sleep(10)
            Logger.debug("Avahi daemon restarted successfully, continuing")
            return True

        except Exception as e:
            Logger.error(f"Error restarting networking service: {e}")
            return False
        
    def change_network_settings_to_master(self):


        try:
            source = os.path.join(TEMPLATES_PATH, CONTROLLER_INTERFACES_TEMPLATE)
            target = '/etc/network/interfaces'
            shutil.copy2(source, target)
        except Exception as e:
            Logger.error(f"Error copying interfaces file: {e}")