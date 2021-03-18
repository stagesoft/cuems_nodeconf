import enum



class CuemsNodeDict(dict):

    @property
    def masters(self):
        master_list = list()

        for node in super().values():
            if node.node_type == CuemsNode.NodeType.master:
                master_list.append(node)
        return master_list
    @property
    def slaves(self):
        slave_list = list()

        for node in super().values():
            if node.node_type == CuemsNode.NodeType.slave:
                slave_list.append(node)
        return slave_list
        
    @property
    def firstruns(self):
        firstrun_list = list()

        for node in super().values():
            if node.node_type == CuemsNode.NodeType.firstrun:
                firstrun_list.append(node)
        return firstrun_list
        
class CuemsNode(dict):

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
    def port(self):
        return super().__getitem__('port')

    @port.setter
    def port(self, value):
        return super().__setitem__('port', value)

    @property
    def uuid(self):
        return super().__getitem__('uuid')

    @uuid.setter
    def uuid(self, value):
        return super().__setitem__('uuid', value)

    # def __repr__(self):
    #     _dict = str({"name" : super().__getitem__('name'), "present" : super().__getitem__('present')})
    #     return _dict