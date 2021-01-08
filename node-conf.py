
from zeroconf import IPVersion, ServiceInfo, ServiceListener, ServiceBrowser, Zeroconf, ZeroconfServiceTypes
import socket
import time

server = "jump.local."
service_info = ServiceInfo(
        "_cuems-node._tcp.local.",
        "Cuems node service on jump._cuems-node._tcp.local.",
        addresses=[socket.inet_aton("192.168.1.12")],
        port=80,
        server=server,
    )

class MyListener:
    nodes = dict()

    def remove_service(self, zeroconf, type, name):
        print("Service %s removed" % (name,))
        del self.nodes[name]
        print(listener.nodes)

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        print(info.properties)
        self.nodes[name] = info.properties[list(info.properties.keys())[0]].decode("utf-8")
        print("Service %s added, service info: %s" % (name, info))
        print(listener.nodes)

    def update_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        self.nodes[name] = info.properties[list(info.properties.keys())[0]].decode("utf-8")
        print("Service %s updated, service info: %s" % (name, info))
        print(listener.nodes)

zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
# services = ["_cuems_node._tcp.local.", "_cuems-nodeconf._tcp.local."]
services = ["_cuems-node._tcp.local."]
#services = ["_cuems-nodeconf._tcp.local."]
listener = MyListener()

browser = ServiceBrowser(zeroconf, services, listener)

def find_master(nodes):
    if 'master' in nodes.values():
        return True
    else:
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
        "Cuems node service on jump._cuems-node._tcp.local.",
        addresses=[socket.inet_aton("192.168.1.12")],
        port=80,
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
    print(listener.nodes)
    input("Press enter to exit...\n\n")
    
finally:
    print("Unregistering...")
    zeroconf.unregister_service(service_info)
    zeroconf.close()


