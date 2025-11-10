from CuemsNode import CuemsNodeDict, CuemsNode
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

    def __init__(self, ip, callback = None):
        self.ip = ip
        self.callback = callback
        self.logger = logging.getLogger('Avahi-listener')

    def get_mac(self, name):
        return name[:12]

    def remove_service(self, zeroconf, type_, name):
        self.logger.debug(f'Service {name} removed')

        if self.callback:
            self.callback(action=CuemsAvahiListener.Action.DELETE)

    def add_service(self, zeroconf, type_, name):
        ip = None
        info = zeroconf.get_service_info(type_, name)
        self.logger.debug(info)
        
        if len(info.parsed_addresses()) > 1:
            self.logger.debug(f'Multiple addresses found for {name}!')
            ## if ip is one of the internal interfaces, use that one, if not use the first one
            for address in info.parsed_addresses():
                if address == self.ip:
                    ip = address
            if not ip:
                ip = info.parsed_addresses()[0]
        else:
            ip = info.parsed_addresses()[0]

        self.logger.debug(f'node ip: {ip}')
        node = CuemsNode({ 'uuid' : info.properties[b"uuid"].decode("utf-8"), 'mac' : self.get_mac(name), 'name' : name, 'node_type': CuemsNode.NodeType[info.properties[b'node_type'].decode("utf-8")] , 'ip' : ip, 'port': info.port, 'adopted': False, 'online': True})
        try:
            self.nodes[self.get_mac(name)].update(node)
        except KeyError:
            self.nodes[self.get_mac(name)] = node
        
        self.logger.debug(f'Service {name} added, service info: {info}')

        if self.callback:
            self.callback(node)

    def update_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        if len(info.parsed_addresses()) > 1:
            self.logger.debug(f'Multiple addresses found for {name}!')
            for address in info.parsed_addresses():
                if address == self.ip:
                    ip = address
        else:
            ip = info.parsed_addresses()[0] 
        node = CuemsNode({ 'uuid' : info.properties[b"uuid"].decode("utf-8"), 'name' : name, 'node_type': CuemsNode.NodeType[info.properties[list(info.properties.keys())[0]].decode("utf-8")], 'ip' : ip, 'port': info.port, 'adopted': False, 'online': True})
        self.nodes[self.get_mac(name)].update(node)
        self.logger.debug(f'Service {name} updated, service info: {info}')

        if self.callback:
            self.callback(node, action=CuemsAvahiListener.Action.UPDATE)