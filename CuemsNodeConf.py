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
import NodeXmlBuilders  # Register custom XML builders for node_list and node

from cuemsutils.xml.XmlReaderWriter import XmlReader, XmlWriter
from cuemsutils.timeoutloop import Timeoutloop
from cuemsutils.log import Logger, logged
from cuemsutils.helpers import strtobool
from communicate import AsyncCommsThread, TIMEOUT
import asyncio


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
        self.network_map = CuemsNodeDict()

        self.services = ['_cuems_nodeconf._tcp.local.']
        

         #TODO: add timeout for the waiting loops
    def stop():
        pass
        exit(-1)

    def start(self):
        Logger.debug('Starting CuemsNodeConf')
        self.set_comms()
        self.run()


    def set_comms(self):
        Logger.info('Setting up Communicators')
        self.communications_thread = AsyncCommsThread(self.engine_callback)
        self.communications_thread.start()

    def engine_callback(self, message, context):
        try:
            action = message.get('action')
            if action == 'nodelist_modify':
                node_uuid = message.get('value')
                modify_action = message.get('modify_action')
                
                if modify_action == 'ADD':
                    result = self.adopt_node(node_uuid)
                elif modify_action == 'REMOVE':
                    result = self.unadopt_node(node_uuid)
                else:
                    result = {'OK': False, 'error': f'Invalid modify_action: {modify_action}'}
                
                response = {'OK': result.get('OK', False)}
                if 'error' in result:
                    response['error'] = result['error']
                
                asyncio.run_coroutine_threadsafe(
                    self.communications_thread.respond_to_engine(response, context),
                    self.communications_thread.event_loop
                )
                return
        except Exception as e:
            Logger.error(f'Error in engine_callback: {e}')
            Logger.exception(e)
            error_response = {'OK': False, 'error': str(e)}
            asyncio.run_coroutine_threadsafe(
                self.communications_thread.respond_to_engine(error_response, context),
                self.communications_thread.event_loop
            )

    def run(self):
        Logger.debug('Running CuemsNodeConf')
        try:
            self.get_ips()
        except TimeoutError:
            Logger.critical('Could not find network interfaces within timeout')
            sys.exit(-1)
        
        # Validate that IP was obtained
        if self.ip is None:
            Logger.critical('Failed to obtain network IP address. Cannot continue.')
            sys.exit(-1)

        self.is_first_run = not os.path.isfile(self.map_path)
        if not self.is_first_run:
            Logger.debug('Reading existing network_map.xml')
            self.read_network_map()
        else:
            Logger.debug('No existing network_map.xml found, starting fresh')
            self.network_map = CuemsNodeDict()

        self.zeroconf = Zeroconf(interfaces=[self.ip],ip_version=IPVersion.V4Only)

        self.start_avahi_listener()
        
        # Wait for local service to be registered and discovered
        Logger.debug('Waiting for local service registration...')
        try:
            self.wait_for_local_service_registration()
        except TimeoutError:
            Logger.critical('Local service did not register within timeout period')
            sys.exit(-1)
        
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
        # Add timeout to prevent infinite loop
        max_iterations = 60  # 30 seconds max (60 * 0.5)
        iteration = 0
        while self.listener.nodes.firstruns and iteration < max_iterations:
            time.sleep(0.5)
            iteration += 1
        if iteration >= max_iterations and self.listener.nodes.firstruns:
            Logger.warning('Timeout waiting for firstrun nodes to resolve. Continuing anyway.')

        self.check_nodes()

        self.merge_discovered_nodes()
        self.set_master_always_adopted()
        self.check_missing_adopted_nodes()

        try:
            self.write_network_map(self.network_map)
        except PermissionError as e:
            Logger.error(f"Permission denied writing network map to {self.map_path}: {e}")
            Logger.exception(e)
        except Exception as e:
            Logger.error(f"Error writing network map: {type(e).__name__}: {e}")
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

    def set_node_type(self):
        if not self.listener.nodes.masters:
            Logger.debug('No master node on the network, I become MASTER!')
            self.node.node_type = CuemsNode.NodeType.master

            # Copy master node service template
            source = os.path.join(TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.master'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)

            try:
                shutil.copy2(source, target)
            except FileNotFoundError:
                Logger.error(f"Master service template not found at {source}")
                raise
            except PermissionError:
                Logger.error(f"Permission denied copying service template to {target}")
                raise
            except Exception as e:
                Logger.error(f"Error copying master service template: {type(e).__name__}: {e}")
                Logger.exception(e)
                raise
            
            if not self.change_network_to_master():
                Logger.error("Failed to change network to master configuration")
                raise RuntimeError("Network configuration change failed")
            
            try:
                self.get_ips()
            except TimeoutError:
                Logger.error("Failed to get IP addresses after network change")
                raise
        else:
            Logger.debug('Master present on the in network WE STAY SLAVE')
            self.node.node_type = CuemsNode.NodeType.slave

            # Copy slave node service template
            source = os.path.join(TEMPLATES_PATH, CUEMS_SERVICE_FILE) + '.slave'
            target = os.path.join('/etc/avahi/services/', CUEMS_SERVICE_FILE)
            try:
                result = os.system(f'sudo cp {source} {target}')
                if result != 0:
                    Logger.error(f"Failed to copy slave service template (exit code: {result})")
                    raise RuntimeError(f"Failed to copy slave service template")
            except Exception as e:
                Logger.error(f"Error copying slave service template: {type(e).__name__}: {e}")
                Logger.exception(e)
                raise
        
    def write_network_map(self, map=None):
        if not map:
            map = self.network_map if hasattr(self, 'network_map') and self.network_map else self.listener.nodes

        # Validate and prepare nodes before writing
        required_fields = ['uuid', 'mac', 'name', 'node_type', 'ip']
        for mac, node in map.items():
            for field in required_fields:
                value = node.get(field)
                if value is None:
                    Logger.error(f"Node {mac} has None value for required field '{field}'. Node data: {dict(node)}")
                    raise ValueError(f"Cannot write network map: Node {mac} has None value for required field '{field}'")
            
            # Ensure node_type is stored as string name, not enum object
            if hasattr(node.get('node_type'), 'name'):
                node['node_type'] = node['node_type'].name
            
            # Ensure adopted and online are properly set as booleans
            # XmlWriter will convert these to 'True'/'False' strings as per BoolType in XSD
            if 'adopted' not in node:
                node['adopted'] = False
            elif isinstance(node['adopted'], str):
                # Convert string to boolean if needed (from old XML files)
                try:
                    node['adopted'] = strtobool(node['adopted'])
                except ValueError:
                    node['adopted'] = False
            
            if 'online' not in node:
                node['online'] = False
            elif isinstance(node['online'], str):
                # Convert string to boolean if needed (from old XML files)
                try:
                    node['online'] = strtobool(node['online'])
                except ValueError:
                    node['online'] = False

        writer = XmlWriter(schema_name = self.xsd_path, xmlfile = self.map_path, xml_root_tag='CuemsNetworkMap')
        writer.write_from_object(map)
        Logger.debug("Network map written to XML")

    def merge_discovered_nodes(self):
        Logger.debug('Merging discovered nodes with network_map')
        discovered_macs = set(self.listener.nodes.keys())
        
        for mac, discovered_node in self.listener.nodes.items():
            if mac in self.network_map:
                existing_node = self.network_map[mac]
                preserved_adopted = existing_node.adopted
                self.network_map[mac].update(discovered_node)
                self.network_map[mac].adopted = preserved_adopted
                self.network_map[mac].online = True
                Logger.debug(f'Merged node {mac}, preserved adopted={preserved_adopted}')
            else:
                self.network_map[mac] = discovered_node
                self.network_map[mac].adopted = False
                self.network_map[mac].online = True
                Logger.debug(f'Added new discovered node {mac}')
        
        for mac, node in self.network_map.items():
            if mac not in discovered_macs:
                node.online = False
                Logger.debug(f'Node {mac} is offline')

    def set_master_always_adopted(self):
        for mac, node in self.network_map.items():
            if node.node_type == CuemsNode.NodeType.master:
                node.adopted = True
                Logger.debug(f'Set master node {mac} as always adopted')
        
        if self.is_first_run:
            for mac, node in self.network_map.items():
                if node.node_type != CuemsNode.NodeType.master:
                    node.adopted = False

    def check_missing_adopted_nodes(self):
        adopted_nodes = [node for node in self.network_map.values() if node.adopted]
        discovered_uuids = {node.uuid for node in self.listener.nodes.values()}
        
        missing_adopted = []
        for node in adopted_nodes:
            if node.uuid not in discovered_uuids:
                missing_adopted.append(node)
        
        if missing_adopted:
            Logger.warning(f'Missing adopted nodes: {[f"{n.name} ({n.uuid})" for n in missing_adopted]}')
        else:
            Logger.debug('All adopted nodes are present')

    def adopt_node(self, node_uuid):
        for node in self.network_map.values():
            if node.uuid == node_uuid:
                # Check if node is already adopted
                if node.adopted:
                    Logger.debug(f'Node {node_uuid} is already adopted')
                    return {'OK': True, 'message': 'Node already adopted'}
                
                # Check if node is online
                if not node.online:
                    Logger.warning(f'Cannot adopt node {node_uuid}: node is offline')
                    return {'OK': False, 'error': f'Cannot adopt node {node_uuid}: node is offline'}
                
                node.adopted = True
                self.write_network_map(self.network_map)
                Logger.info(f'Node {node_uuid} adopted')
                return {'OK': True}
        
        Logger.warning(f'Node {node_uuid} not found in network_map')
        return {'OK': False, 'error': f'Node {node_uuid} not found'}

    def unadopt_node(self, node_uuid):
        for node in self.network_map.values():
            if node.uuid == node_uuid:
                if node.node_type == CuemsNode.NodeType.master:
                    Logger.warning(f'Cannot unadopt master node {node_uuid}')
                    return {'OK': False, 'error': 'Cannot unadopt master node'}
                
                # Check if node is already unadopted
                if not node.adopted:
                    Logger.debug(f'Node {node_uuid} is already unadopted')
                    return {'OK': True, 'message': 'Node already unadopted'}
                
                # Note: Offline nodes can and should be unadoptable
                # This allows cleaning up nodes that have gone offline
                if not node.online:
                    Logger.info(f'Unadopting offline node {node_uuid} (node is not online)')
                
                node.adopted = False
                self.write_network_map(self.network_map)
                Logger.info(f'Node {node_uuid} unadopted')
                return {'OK': True}
        
        Logger.warning(f'Node {node_uuid} not found in network_map')
        return {'OK': False, 'error': f'Node {node_uuid} not found'}

    def read_network_map(self):
        reader = XmlReader(schema_name = self.xsd_path, xmlfile = self.map_path)
        self.network_map = CuemsNodeDict()
        nodes = reader.read_to_objects()
        for node in nodes:
            # Normalize node_type - handle both "master" and "NodeType.master" formats
            if 'node_type' in node:
                node_type_str = str(node['node_type'])
                # Remove "NodeType." prefix if present
                if node_type_str.startswith('NodeType.'):
                    node_type_str = node_type_str.replace('NodeType.', '')
                # Convert to enum
                try:
                    node['node_type'] = CuemsNode.NodeType[node_type_str]
                except KeyError:
                    Logger.error(f"Invalid node_type '{node_type_str}' for node {node.get('mac', 'unknown')}")
                    # Default to slave if invalid
                    node['node_type'] = CuemsNode.NodeType.slave
            
            # Note: Boolean fields are already parsed by CuemsParser using strtobool
            # No additional conversion needed - they come as Python bool from read_to_objects()
            
            self.network_map[node.mac] = node
        
        Logger.debug("---")
        Logger.debug("Nodes read from existing XML network map:")
        for item, value in self.network_map.items():
            Logger.debug(f"{value}")
        Logger.debug("---")

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
    
    def wait_for_local_service_registration(self):
        """
        Wait for the local service to be registered and discovered by the Avahi listener.
        This ensures the service is available before we try to retrieve it.
        """
        for passed in Timeoutloop(timeout=5, interval=0.2):
            for node in self.listener.nodes.values():
                if node.ip == self.ip:
                    Logger.debug(f'Local service registered and discovered: {node.name}')
                    return
            
            Logger.debug("Waiting for local service to be registered...")
        
        # Timeout occurred - Timeoutloop will raise TimeoutError
        raise TimeoutError('Local service registration not detected within timeout period')

    def retreive_local_node(self):
        for passed in Timeoutloop(timeout=10, interval=1):
            for node in self.listener.nodes.values():
                if node.ip == self.ip:
                    return node

            Logger.debug("waiting for local node to appear on the network")
        
        # Timeout occurred - Timeoutloop will raise TimeoutError
        raise TimeoutError('Local node not found within timeout period')
        

    def publish_master_alias(self):
        try:
            if self.ip is None:
                Logger.warning(f"Cannot publish {MASTER_ALIAS} alias: IP address is None")
                return
            subprocess.Popen(["avahi-publish", "-aR", MASTER_ALIAS, self.ip], close_fds=True)
            Logger.debug(f"Publishing {MASTER_ALIAS} alias in {self.ip}")
        except FileNotFoundError:
            Logger.error(f"avahi-publish command not found. Cannot publish {MASTER_ALIAS} alias")
        except Exception as e:
            Logger.error(f"Error publishing {MASTER_ALIAS} alias: {type(e).__name__}: {e}")
            Logger.exception(e)

    def publish_controller_alias(self):
        try:
            if self.controller_ip is None:
                Logger.warning(f"Cannot publish {CONTROLLER_ALIAS} alias: controller IP address is None")
                return
            subprocess.Popen(["avahi-publish", "-aR", CONTROLLER_ALIAS, self.controller_ip], close_fds=True)
            Logger.debug(f"Publishing {CONTROLLER_ALIAS} alias in {self.controller_ip}")
        except FileNotFoundError:
            Logger.error(f"avahi-publish command not found. Cannot publish {CONTROLLER_ALIAS} alias")
        except Exception as e:
            Logger.error(f"Error publishing {CONTROLLER_ALIAS} alias: {type(e).__name__}: {e}")
            Logger.exception(e)

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
            
            try:
                self.change_network_settings_to_master()
            except Exception as e:
                Logger.error(f"Error changing network settings: {e}")
                Logger.exception(e)
                return False
            
            job = manager.StartUnit('networking.service', 'fail')
            Logger.debug("Starting networking service")
            time.sleep(10)
            Logger.debug("Networking service restarted successfully")
            
            try:
                job = manager.StartUnit('avahi-daemon.service', 'fail')
                time.sleep(10)
                Logger.debug("Avahi daemon restarted successfully, continuing")
            except Exception as e:
                Logger.warning(f"Error restarting avahi-daemon service: {e}")
                Logger.exception(e)
                # Continue anyway as this is not critical
            
            return True

        except dbus.exceptions.DBusException as e:
            Logger.error(f"DBus error restarting networking service: {e}")
            Logger.exception(e)
            return False
        except Exception as e:
            Logger.error(f"Error restarting networking service: {type(e).__name__}: {e}")
            Logger.exception(e)
            return False
        
    def change_network_settings_to_master(self):


        try:
            source = os.path.join(TEMPLATES_PATH, CONTROLLER_INTERFACES_TEMPLATE)
            target = '/etc/network/interfaces'
            shutil.copy2(source, target)
        except Exception as e:
            Logger.error(f"Error copying interfaces file: {e}")