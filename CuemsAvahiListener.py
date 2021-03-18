from .CuemsNode import CuemsNodeDict, CuemsNode
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

    def get_uuid(self, name):
        return name[:12]

    def remove_service(self, zeroconf, type_, name):
        self.logger.debug(f'Service {name} removed')

        if self.callback:
            self.callback(action=CuemsAvahiListener.Action.DELETE)

    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        self.logger.debug(info)
        node = CuemsNode({ 'uuid' : self.get_uuid(name), 'name' : name, 'node_type': CuemsNode.NodeType[info.properties[list(info.properties.keys())[0]].decode("utf-8")] , 'ip' : info.parsed_addresses()[0], 'port': info.port})
        try:
            self.nodes[self.get_uuid(name)].update(node)
        except KeyError:
            self.nodes[self.get_uuid(name)] = node
        
        self.logger.debug(f'Service {name} added, service info: {info}')

        if self.callback:
            self.callback(node)

    def update_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        node = CuemsNode({ 'uuid' : self.get_uuid(name), 'name' : name, 'node_type': CuemsNode.NodeType[info.properties[list(info.properties.keys())[0]].decode("utf-8")], 'ip' : info.parsed_addresses()[0], 'port': info.port})
        self.nodes[self.get_uuid(name)].update(node)
        self.logger.debug(f'Service {name} updated, service info: {info}')

        if self.callback:
            self.callback(node, action=CuemsAvahiListener.Action.UPDATE)