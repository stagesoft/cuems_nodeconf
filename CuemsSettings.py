import socket
import netifaces
import uuid
from .CuemsNode import CuemsNode


def get_ip():
    iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
    return netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']

def read_conf():
    # TEMP FIXX
    iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
    mac = netifaces.ifaddresses(iface)[netifaces.AF_LINK][0]['addr']
    mac = f"MAC_instead_of_UUID{mac}"

    settings_dict = dict()
    settings_dict['ip'] = get_ip()
    settings_dict['uuid'] = mac
    #settings_dict['uuid'] = str(uuid.uuid4())
    settings_dict['hostname'] = socket.gethostname()
    settings_dict['server'] = f"{settings_dict['hostname']}.local."
    settings_dict['type_'] = "_cuems_nodeconf._tcp.local."
    settings_dict['name'] = f"{settings_dict['uuid']} Cuems node on {settings_dict['hostname']}._cuems-nodeconf._tcp.local."
    settings_dict['port'] = 9000
    settings_dict['properties'] = {'node_type' : CuemsNode.NodeType.slave}
    settings_dict['host_ttl'] = 50
    settings_dict['other_ttl'] = 50

    return settings_dict
