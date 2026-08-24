import time
import enum

from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes

from cuemsutils.tools.NodeList import NodeRole

SERVICES = ['_cuems_nodeconf._tcp.local.', '_cuems_osc._tcp.local.']

# feature 007: the duplicate NodeType enum this file used to define is gone —
# NodeRole is the one definition (contract C1). The Avahi TXT record's own
# key/value ('node_type=master' etc.) is UNCHANGED (deferred to feature 008,
# spec Assumption 10), so a lookup by *name* against NodeRole (whose members
# are spelled controller/node/firstrun) cannot resolve "master"/"slave" the
# way the old NodeType[...] lookup could. This manual debug tool (unreferenced
# by any production code path — confirmed via repo-wide search, FR-018) is
# fixed to decode through the same wire-to-model mapping
# CuemsAvahiListener.py uses, rather than left silently broken.
_AVAHI_NODE_TYPE_TO_ROLE = {
    'master': NodeRole.controller,
    'slave': NodeRole.node,
    'firstrun': NodeRole.firstrun,
}


def _decode_role(raw: str) -> str:
    """The TXT record's raw value, as a human-readable role label.

    Falls back to the raw string for a value neither the legacy nor the
    current vocabulary recognises, rather than raising — this is a debug
    print tool; a KeyError here would just be a worse way to say "unknown".
    """
    role = _AVAHI_NODE_TYPE_TO_ROLE.get(raw)
    return role.value if role is not None else f"{raw} (unrecognised)"

class MyAvahiListener():
    @enum.unique
    class Action(enum.Enum):
        DELETE = 0
        ADD = 1
        UPDATE = 2

    def __init__(self, callback = None):
        self.callback = callback
        self.services = {}

    def remove_service(self, zeroconf, type_, name):
        print('________________________________________________________________________')
        print('Service REMOVED')
        print(f'Name : {name}')

        try:
            self.services.pop(name)
        except KeyError:
            pass

        self.print_current_present_nodes()

        if self.callback:
            self.callback(action=MyAvahiListener.Action.DELETE)

    def add_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        self.services[name] = info
        print('________________________________________________________________________')
        print('Service ADDED')
        print(f'Name : {name}')
        self.print_node_info(info)

        if self.callback:
            self.callback(node)

    def update_service(self, zeroconf, type_, name):
        info = zeroconf.get_service_info(type_, name)
        self.services[name] = info
        print('________________________________________________________________________')
        print('Service UPDATED')
        print(f'Name : {name}')
        self.print_node_info(info)

        if self.callback:
            self.callback(node, action=MyAvahiListener.Action.UPDATE)

    def print_node_info(self, info):
        print(f'SERVICE: {info.type}')
        print(f'UUID: {info.properties[b"uuid"].decode("utf8")}')
        print(f'MAC: {info.name[:12]}')
        print(f'Node role: {_decode_role(info.properties[list(info.properties.keys())[0]].decode("utf-8"))}')
        print(f'IP: {info.parsed_addresses()[0]}')
        print(f'Port: {info.port}')
        print(f'Whole info: {info}')

        self.print_current_present_nodes()

    def print_current_present_nodes(self):
        print('________________________________________________________________________')
        print(f'CURRENT PRESENT NODECONF NODES:')
        for key, value in self.services.items():
            if value.type == '_cuems_nodeconf._tcp.local.':
                print(f'{value.parsed_addresses()[0]} : {value.port} - {_decode_role(value.properties[list(value.properties.keys())[0]].decode("utf-8"))}')
        print(f'\nCURRENT PRESENT OSC NODES:')
        for key, value in self.services.items():
            if value.type == '_cuems_osc._tcp.local.':
                print(f'{value.parsed_addresses()[0]}  : {value.port} - {_decode_role(value.properties[list(value.properties.keys())[0]].decode("utf-8"))}')
        




class AvahiTool():
    def __init__(self):
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        self.services = SERVICES

        self.listener = MyAvahiListener()
        self.browser = ServiceBrowser(self.zeroconf, self.services, self.listener)
        time.sleep(2)

    def callback(self, caller_node=None, action=MyAvahiListener.Action.ADD):
        print(f" {action} callback!!!, Node: {caller_node} ")

    def shutdown(self):
        self.zeroconf.close()



if __name__ == "__main__":
    print('Cuems Avahi Tool - StageLab Coop')
    print('This little tool will show all the CUEMS avahi zeroconf services')
    print('on the net and their changes when they appear, update or disappear')
    print('It will end when you press a key.')
    print('________________________________________________________________________')
    print(f'This is the list of services we are looking for: {SERVICES}\n')
    myAvahiTool = AvahiTool()
    a = input()
    if a:
        exit(0)
