import enum

@enum.unique
class NodeType(enum.Enum):
    slave = 0
    master = 1

class CuemsNodeDict(dict):

    slave_list = list()
    master_node = None

    def __setitem__(self, k, v):
        if v.node_type == "slave":
            self.slave_list.append(v)
        else:
            self.master_node = v


        return super().__setitem__(k, v)

    
    
    @property
    def master(self):
        return self.master_node

    @property
    def slaves(self):
        return self.slave_list
        
    

class CuemsNode(dict):
    
    @property
    def node_type(self):
        return super().__getitem__('node_type')

    @property
    def name(self):
        return super().__getitem__('name')

    @property
    def ip(self):
        return super().__getitem__('ip')

    @property
    def port(self):
        return super().__getitem__('port')

    def __repr__(self):
        return super().__getitem__('node_type')

