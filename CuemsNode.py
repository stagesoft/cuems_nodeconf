# SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later

import enum



class node_list(dict):

    @property
    def masters(self):
        master_list = list()

        for node_obj in super().values():
            if node_obj.node_type == node.NodeType.master:
                master_list.append(node_obj)
        return master_list
    @property
    def slaves(self):
        slave_list = list()

        for node_obj in super().values():
            if node_obj.node_type == node.NodeType.slave:
                slave_list.append(node_obj)
        return slave_list
        
    @property
    def firstruns(self):
        firstrun_list = list()

        for node_obj in super().values():
            if node_obj.node_type == node.NodeType.firstrun:
                firstrun_list.append(node_obj)
        return firstrun_list
        
class node(dict):

    @enum.unique
    class NodeType(enum.Enum):
        slave = 0
        master = 1
        firstrun = 2

        def __repr__(self):
            return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    @property
    def node_type(self):
        return super().__getitem__('node_type')
    
    @node_type.setter
    def node_type(self, value):
        return super().__setitem__('node_type', value)

    @property
    def name(self):
        return super().__getitem__('name')

    @name.setter
    def name(self, value):
        return super().__setitem__('name', value)

    @property
    def ip(self):
        return super().__getitem__('ip')

    @ip.setter
    def ip(self, value):
        return super().__setitem__('ip', value)

    @property
    def uuid(self):
        return super().__getitem__('uuid')

    @uuid.setter
    def uuid(self, value):
        return super().__setitem__('uuid', value)

    @property
    def mac(self):
        return super().__getitem__('mac')

    @mac.setter
    def mac(self, value):
        return super().__setitem__('mac', value)

    @property
    def adopted(self):
        return super().get('adopted', False)

    @adopted.setter
    def adopted(self, value):
        return super().__setitem__('adopted', value)

    @property
    def online(self):
        return super().get('online', False)

    @online.setter
    def online(self, value):
        return super().__setitem__('online', value)

    # def __repr__(self):
    #     _dict = str({"name" : super().__getitem__('name'), "present" : super().__getitem__('present')})
    #     return _dict

# Backwards compatibility aliases
CuemsNodeDict = node_list
CuemsNode = node
