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

CUEMS_CONF_PATH = '/etc/cuems/'

logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )


class CuemsNodeConf():
    nodes = CuemsNodeDict()

    def __init__(self, settings_dict=read_conf()):
        self.logger = logging.getLogger('Cuems-NodeConf')
        self.init_done = False
        self.master = False

        # Conf load manager
        try:
            self.cm = ConfigManager(path=CUEMS_CONF_PATH)
        except FileNotFoundError:
            self.logger.critical('Node config file could not be found. Exiting !!!!!')
            exit(-1)
        
        
        

        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        self.settings_dict = settings_dict
        self.services = [self.settings_dict['type_']]

        

        self.node = CuemsNode()

        # if autoconf file exists mark first time conf
        self.first_time = os.path.isfile(os.path.join(CUEMS_CONF_PATH, self.cm.autoconf_lock_file))
        self.logger.debug(os.path.join(CUEMS_CONF_PATH, self.cm.autoconf_lock_file))
        self.logger.debug(self.first_time)

        self.start_avahi_listener()


        if self.first_time:
            self.logger.debug("First time conf file detected, triying to autoconfigure node")
            self.set_node_type()
            self.create_network_map()
        else:
            self.read_conf()
            
            if self.master:
                self.read_network_map()
                self.check_network_map()

        
        self.register_node()
        
        #time.sleep(2)
        self.check_nodes()

        self.init_done = True


    def start_avahi_listener(self):
        self.listener = CuemsAvahiListener(callback= self.callback)
        self.browser = ServiceBrowser(self.zeroconf, self.services, self.listener)
        time.sleep(2)

    def read_conf(self):
        pass

    def create_network_map(self):
        pass

    def read_network_map(self):
        pass

    def check_network_map(self):
        pass

    def set_node_type(self):
        self.master_exists = self.find_master()

        if not self.master_exists:
            self.logger.debug('No Master in network, WE ARE MASTER')
            self.node.node_type = 'master'
        else:
            self.node.node_type = 'slave'
            self.logger.debug('Master present in network WE STAY SLAVE')


    def cleanup(self):
        try:
            os.remove(os.path.join(CUEMS_CONF_PATH, self.cm.autoconf_lock_file))
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
        if self.node.node_type == 'master' and self.listener.nodes.slaves:
            if caller_node:
                if caller_node.node_type == "master":
                    self.logger.debug("Node is master, ignore")
                    return None
                if caller_node.configured == True:
                    self.logger.debug("Node is allready configured, ignore")
                    return None
                slaves_to_ask = [caller_node]
            else:
                slaves_to_ask = self.listener.nodes.slaves

            self.logger.debug(self.listener.nodes.slaves)


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
        
        self.settings_dict['properties']['node_type'] = self.node.node_type

        self.service_info = ServiceInfo(
            self.settings_dict['type_'],
            self.settings_dict['name'],
            addresses = [self.settings_dict['ip']],
            port = self.settings_dict['port'],
            properties= {'node_type' : self.node.node_type },
            server = self.settings_dict['server'],
            host_ttl=self.settings_dict['host_ttl'],
            other_ttl=self.settings_dict['other_ttl'],

        )
        self.logger.debug(f"registering node as {self.node.node_type.upper()}")
        self.zeroconf.register_service(self.service_info)
        self.logger.debug("Node registered")


    def shutdown(self):
        self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()