import enum



class CuemsNodeDict(dict):

    @property
    def master(self):
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
        
    

class CuemsNode(dict):

    @enum.unique
    class NodeType(enum.Enum):
        slave = 0
        master = 1

        def __repr__(self):
            return self.name


    def __init__(self, *args, **kwargs):
        self.present = False
        super().__init__(*args, **kwargs)
    
    @property
    def node_type(self):
        return super().__getitem__('node_type')
    
    @node_type.setter
    def node_type(self, value):
        return super().__setitem__('node_type', value)


    @property
    def present(self):
        return super().__getitem__('present')
    
    @present.setter
    def present(self, value):
        return super().__setitem__('present', value)


    @property
    def name(self):
        return super().__getitem__('name')


    @property
    def ip(self):
        return super().__getitem__('ip')

    @property
    def port(self):
        return super().__getitem__('port')

    @property
    def uuid(self):
        return super().__getitem__('uuid')

    # def __repr__(self):
    #     _dict = str({"name" : super().__getitem__('name'), "present" : super().__getitem__('present')})
    #     return _dict