
import socket
import netifaces
import uuid
import threading
import time

from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes

import logging

from CuemsNode import CuemsNodeDict, CuemsNode, NodeType
from CuemsConfServer import CuemsConfServer

logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )

def get_ip():
    iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
    return netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']

def read_conf():
    settings_dict = dict()
    settings_dict['ip'] = socket.inet_aton(get_ip())
    settings_dict['uuid'] = str(uuid.uuid4())
    settings_dict['hostname'] = socket.gethostname()
    settings_dict['server'] = f"{settings_dict['hostname']}.local."
    settings_dict['type_'] = "_cuems-nodeconf._tcp.local."
    settings_dict['name'] = f"{settings_dict['uuid']} Cuems node on {settings_dict['hostname']}._cuems-nodeconf._tcp.local."
    settings_dict['port'] = 9000
    #settings_dict['properties'] = {'node_type' : NodeType.slave}
    settings_dict['properties'] = {'node_type' : 'slave'}
    settings_dict['host_ttl'] = 10
    settings_dict['other_ttl'] = 10

    return settings_dict


class CuemsNodeConf():

    def __init__(self, settings_dict=read_conf()):
        self.logger = logging.getLogger('Cuems-NodeConf')
        self.client_running = False
        self.server_running = False
        self.client_retryes = 6
        self.client_retry_count_delay = 6
        self.client_retry_count = 0
        self.master = False
        self.init_done = False
        self.settings_dict = settings_dict
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self.services = [self.settings_dict['type_']]
        self.listener = CuemsAvahiListener(callback= self.callback)
        self.browser = ServiceBrowser(self.zeroconf, self.services, self.listener)
        time.sleep(2)
        self.master_exists = self.find_master()

        if not self.master_exists:
            self.logger.debug('No Master in network, WE ARE MASTER')
            self.master = True
        else:
            self.logger.debug('Master present in network WE STAY SLAVE')

        self.register_node()
        #time.sleep(2)
        self.check_nodes()

        if self.master:
            self.start_server()
        else: 
            self.client_retry()

        self.init_done = True

        
    def client_retry(self):
        self.client_running = True
        
        while self.client_retry_count <= self.client_retryes:
            self.logger.debug(self.client_retry_count)
            try:
                self.start_client()
            except Exception as e:
                self.logger.debug(e)
            else:
                self.logger.debug("succesfull connect, exiting retry loop")
                break
            finally:
                self.logger.debug("closing client")
                self.close_client()
            self.client_retry_count += 1
            time.sleep(self.client_retry_count_delay)
            
        self.logger.debug("end client retries")
        self.client_running = False


    def callback(self):
        #self.logger.debug("callback!!! ")
        if not self.master and self.init_done:
            self.client_retry_count = 0
            if self.client_running:
                self.logger.debug("reseting client retries")
            else:
                self.logger.debug("callback starting client ")
                self.client_thread = threading.Thread(target=self.client_retry)
                self.client_thread.start()

            
            

    def find_master(self):
        for node in self.listener.nodes.values():
            self.logger.debug(node)
            if 'master' in node.values():
                return True
        return False

    def check_nodes(self):
        self.logger.debug(self.listener.nodes)
        if self.listener.nodes.master:
            self.logger.debug(f"master: {self.listener.nodes.master}")
        else:
            raise Exception("we have no master!!")
        if self.listener.nodes.slaves:
            self.logger.debug(f"we have {len(self.listener.nodes.slaves)} slaves")
            self.logger.debug("slaves: {listener.nodes.slaves}")
        else:
            self.logger.debug("we have no slaves")



    def register_node(self):
        if self.master:
            self.settings_dict['properties']['node_type'] = "master"

        self.service_info = ServiceInfo(
            self.settings_dict['type_'],
            self.settings_dict['name'],
            addresses = [self.settings_dict['ip']],
            port = self.settings_dict['port'],
            properties= self.settings_dict['properties'],
            server = self.settings_dict['server'],
            host_ttl=self.settings_dict['host_ttl'],
            other_ttl=self.settings_dict['other_ttl'],

        )
        self.logger.debug("registering node")
        self.zeroconf.register_service(self.service_info)
        self.logger.debug("Node registered")

    def start_server(self):
        address = (self.settings_dict['server'], self.settings_dict['port'])
        self.server = CuemsConfServer(address)
        ip, port = self.server.server_address
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.setDaemon(True)
        self.server_thread.start()
        self.logger.info('Server on %s:%s', ip, port)

    def start_client(self):
        self.logger.info(f'conecting to master on {self.listener.nodes.master.ip}:{self.listener.nodes.master.port}')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.listener.nodes.master.ip, self.listener.nodes.master.port))
        
        # Send the data
        message = f"Hello from {self.settings_dict['server']}, slave node with uuid: {self.settings_dict['uuid']}".encode()
        self.logger.debug(f'sending data: {message}')
        len_sent = self.socket.send(message)
        
        # Receive a response
        self.logger.debug('waiting for response')
        response = self.socket.recv(len_sent)
        self.logger.debug(f'response from server: {response}')

    def close_server(self):
        self.server.shutdown()
        self.server.socket.close()

    def close_client(self):
        self.socket.close()

    def shutdown(self):
        self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()

        try: 
            self.server.shutdown()
            self.server.socket.close()
        except AttributeError:
            pass

        try:
            self.socket.close()
        except AttributeError:
            pass


class CuemsAvahiListener():
    nodes = CuemsNodeDict()

    def __init__(self, callback = None):
        self.callback = callback
        self.logger = logging.getLogger('Avahi-listener')

    def get_host(self, name):
        return name[51:]

    def get_uuid(self, name):
        return name[:36]
        

    def remove_service(self, zeroconf, type, name):
        self.logger.debug("Service %s removed" % (name,))
        del self.nodes[self.get_host(name)]
        self.logger.debug(self.nodes)

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        self.logger.debug(info)
        self.nodes[self.get_host(name)] = CuemsNode({ 'uuid' : self.get_uuid(name), 'name' : self.get_host(name), 'node_type': info.properties[list(info.properties.keys())[0]].decode("utf-8"), 'ip' : info.parsed_addresses()[0], 'port': info.port})
        self.logger.debug("Service %s added, service info: %s" % (name, info))
        self.logger.debug(self.nodes)
        self.callback()

    def update_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        self.nodes[self.get_host(name)] = CuemsNode({ 'name' : self.get_host(name), 'node_type': info.properties[list(info.properties.keys())[0]].decode("utf-8"), 'ip' : info.parsed_addresses()[0], 'port': info.port}) # TODO: update object, dont make new one ?
        self.logger.debug("Service %s updated, service info: %s" % (name, info))
        self.logger.debug(self.nodes)