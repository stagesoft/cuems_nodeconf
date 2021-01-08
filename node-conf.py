
from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes
import socket
import netifaces
import time
import uuid

iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
ip = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
str_uuid = str(uuid.uuid4())
hostname = socket.gethostname()
server = f"{hostname}.local."
service_info = ServiceInfo(
        "_cuems-node._tcp.local.",
        f"{str_uuid} Cuems node on {hostname}._cuems-node._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=9000,
    )

class MyListener:
    nodes = dict()
    def get_host(self, name):
        return name[51:]

    def get_uuid(self, name):
        return name[:36]
        

    def remove_service(self, zeroconf, type, name):
        print("Service %s removed" % (name,))
        del self.nodes[self.get_uuid(name)]
        print(listener.nodes)

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        self.nodes[self.get_uuid(name)] = { 'name' : self.get_host(name), 'node_type': info.properties[list(info.properties.keys())[0]].decode("utf-8"), 'ip' : info.parsed_addresses()[0], 'port': info.port}
        print("Service %s added, service info: %s" % (name, info))
        print(listener.nodes)

    def update_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        self.nodes[self.get_uuid(name)] = { 'name' : self.get_host(name), 'node_type': info.properties[list(info.properties.keys())[0]].decode("utf-8"), 'ip' : info.parsed_addresses()[0], 'port': info.port}
        print("Service %s updated, service info: %s" % (name, info))
        print(listener.nodes)

zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
# services = ["_cuems_node._tcp.local.", "_cuems-nodeconf._tcp.local."]
services = ["_cuems-node._tcp.local."]
#services = ["_cuems-nodeconf._tcp.local."]
listener = MyListener()

browser = ServiceBrowser(zeroconf, services, listener)

def find_master(nodes):
    for node in nodes.values():
        print(node)
        if 'master' in node.values():
            return True
        
    return False

def register_node(zeroconf_instance, server, service_info, master_exists):
    
    if not master_exists:
        node_type = 'master'
        print("no master in network, We are master!")
    else:
        node_type = 'slave'
        print("master present, We stay as slave")

    service_info = ServiceInfo(
       "_cuems-node._tcp.local.",
        f"{str_uuid} Cuems node on {hostname}._cuems-node._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=9000,
        properties={'node_type' : node_type },
        server=server,
        host_ttl=10,
        other_ttl=10,
    )

    zeroconf_instance.register_service(service_info)    


try:
    time.sleep(2)
    print("Registering service")
    register_node(zeroconf, server, service_info, find_master(listener.nodes))
#    print('\n'.join(ZeroconfServiceTypes.find(zc=zeroconf)))
    input("Press enter to exit...\n\n")
    
finally:
    print("Unregistering...")
    zeroconf.unregister_service(service_info)
    zeroconf.close()


