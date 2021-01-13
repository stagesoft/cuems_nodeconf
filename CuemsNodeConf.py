
import socket
import netifaces
import threading
import time

from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes

import logging

from CuemsConfServer import CuemsConfServer
from CuemsAvahiListener import CuemsAvahiListener
from CuemsNode import CuemsNodeDict

from CuemsSettings import read_conf

logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )


class CuemsNodeConf():
    nodes = CuemsNodeDict()

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

        self.init_done = True

        if self.master:
            self.callback()
        else: 
            self.start_server()

        
    def client_retry(self, node):
        self.client_running = True
        
        while self.client_retry_count <= self.client_retryes:
            self.logger.debug(self.client_retry_count)
            try:
                self.start_client(node)
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
        if self.master and self.init_done and self.listener.nodes.slaves:
            self.logger.debug(self.listener.nodes.slaves)
            for node in self.listener.nodes.slaves:

                self.client_retry_count = 0
                if self.client_running:
                    self.logger.debug("reseting client retries")
                else:
                    self.logger.debug("callback starting client ")
                    self.client_thread = threading.Thread(target=self.client_retry, args=[node,])
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
            self.logger.debug(f"slaves: {self.listener.nodes.slaves}")
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

    def start_client(self, node):
        self.logger.info(f'conecting to slave node on {node.ip}:{node.port}')
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((node.ip, node.port))
        
        # Send the data
        message = f"Hello {self.settings_dict['server']}, master node with uuid: {self.settings_dict['uuid']}".encode()
        self.logger.debug(f'sending data: {message}')
        len_sent = self.socket.send(message)
        
        # Receive a response
        self.logger.debug('waiting for response')
        response = self.socket.recv(len_sent)
        self.logger.debug(f'response from server: {response}')

        # Send the data
        message = f"Conf".encode()
        self.logger.debug(f'sending data: {message}')
        len_sent = self.socket.send(message)
        
        # Receive a response
        self.logger.debug('waiting for response')
        response = self.socket.recv(len_sent)
        self.logger.debug(f'response from server: {response}')

        node['conf']=response
        
        self.nodes[node.uuid] = node
        self.logger.debug(f"CONFIGURED NODES: {self.nodes}")

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