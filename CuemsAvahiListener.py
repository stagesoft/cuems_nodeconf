from .CuemsNode import CuemsNodeDict, CuemsNode, NodeType
import logging


logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )

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