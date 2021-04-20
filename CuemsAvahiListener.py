from .CuemsNode import CuemsNodeDict, CuemsNode
import enum
import logging
from zeroconf import IPVersion


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

    def get_mac(self, name):
        return name[:12]

    def remove_service(self, zeroconf, type_, name):
        self.logger.debug(f'Service {name} removed')

        if self.callback:
            self.callback(action=CuemsAvahiListener.Action.DELETE)

    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        self.logger.debug(info)
        iface_adresses = info.parsed_addresses(version = IPVersion.V4Only)[0]
        print("------------------INFO ADD---------------")
        print(iface_adresses)
        print(type(iface_adresses))
        node = CuemsNode({ 'uuid' : info.properties[b"uuid"].decode("utf-8"), 'mac' : self.get_mac(name), 'name' : name, 'node_type': CuemsNode.NodeType[info.properties[b'node_type'].decode("utf-8")] , 'ip' : [iface_adresses], 'port': info.port})
        try:
            self.nodes[self.get_mac(name)]['uuid'] = info.properties[b"uuid"].decode("utf-8")
            self.nodes[self.get_mac(name)]['mac'] = self.get_mac(name)
            self.nodes[self.get_mac(name)]['name'] = name
            self.nodes[self.get_mac(name)]['node_type'] = CuemsNode.NodeType[info.properties[b'node_type'].decode("utf-8")]
            self.nodes[self.get_mac(name)]['ip'].append(iface_adresses)
            self.nodes[self.get_mac(name)]['port'] = info.port
        except KeyError:
            self.nodes[self.get_mac(name)] = node
        
        self.logger.debug(f'Service {name} added, service info: {info}')

        if self.callback:
            self.callback(node)

    def update_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        iface_adresses = info.parsed_addresses(version = IPVersion.V4Only)[0]
        print("------------------INFO UPDATE--------------")
        print(iface_adresses)
        print(type(iface_adresses))
        self.nodes[self.get_mac(name)]['uuid'] = info.properties[b"uuid"].decode("utf-8")
        self.nodes[self.get_mac(name)]['mac'] = self.get_mac(name)
        self.nodes[self.get_mac(name)]['name'] = name
        self.nodes[self.get_mac(name)]['node_type'] = CuemsNode.NodeType[info.properties[b'node_type'].decode("utf-8")]
        self.nodes[self.get_mac(name)]['ip'].append(iface_adresses)
        self.nodes[self.get_mac(name)]['port'] = info.port
        self.logger.debug(f'Service {name} updated, service info: {info}')

        if self.callback:
            self.callback(node, action=CuemsAvahiListener.Action.UPDATE)