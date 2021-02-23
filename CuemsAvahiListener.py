from .CuemsNode import CuemsNodeDict, CuemsNode, NodeType
import enum
import logging


logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )


class CuemsAvahiListener():
    nodes = CuemsNodeDict()
    @enum.unique
    class Action(enum.Enum):
        DELETE = 0
        ADD = 1
        UPDATE = 2

    def __init__(self, callback = None):
        self.callback = callback
        self.logger = logging.getLogger('Avahi-listener')

    def get_host(self, name):
        return name[51:]

    def get_uuid(self, name):
        return name[:36]
        

    def remove_service(self, zeroconf, type_, name):
        self.logger.debug("Service %s removed" % (name,))
        self.nodes[self.get_uuid(name)].present = False
        self.logger.debug(self.nodes)

    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        self.logger.debug(info)
        node = CuemsNode({ 'uuid' : self.get_uuid(name), 'name' : self.get_host(name), 'node_type': info.properties[list(info.properties.keys())[0]].decode("utf-8"), 'ip' : info.parsed_addresses()[0], 'port': info.port, "present" : True})
        try:
            print("updating")
            print(f"nombre: {name}")
            print(self.nodes)
            self.nodes[self.get_uuid(name)].update(node)
        except KeyError:
            print("keyerror")
            self.nodes[self.get_uuid(name)] = node
        
        self.logger.debug("Service %s added, service info: %s" % (name, info))
        self.logger.debug(self.nodes)
        self.callback(node)

    def update_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        node = CuemsNode({ 'uuid' : self.get_uuid(name), 'name' : self.get_host(name), 'node_type': info.properties[list(info.properties.keys())[0]].decode("utf-8"), 'ip' : info.parsed_addresses()[0], 'port': info.port})
        self.nodes[self.get_uuid(name)].update(node)
        self.logger.debug("Service %s updated, service info: %s" % (name, info))
        self.logger.debug(self.nodes)