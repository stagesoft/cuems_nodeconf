"""
Tests for network map reading, writing, and merging operations.
"""
import pytest
from cuemsnodeconf.CuemsNodeConf import CuemsNodeConf
from cuemsutils.tools.NodeList import NodeIndex, NodeRole, node as Node
from cuemsnodeconf.CuemsAvahiListener import CuemsAvahiListener


class TestNetworkMapOperations:
    """Test network map reading, writing, and merging."""

    def test_merge_discovered_nodes_new_node(self):
        """Test merging when a new node is discovered."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.listener = CuemsAvahiListener(ip='169.254.1.1')

        # Add a discovered node
        discovered_node = Node(
            uuid='new-uuid',
            mac='newmac123456',
            name='new_node',
            node_role=NodeRole.node,
            ip='192.168.1.10',
            online=True,
        )
        nodeconf.listener.nodes['newmac123456'] = discovered_node

        nodeconf.merge_discovered_nodes()

        assert 'newmac123456' in nodeconf.network_map
        assert nodeconf.network_map['newmac123456']['adopted'] is False
        assert nodeconf.network_map['newmac123456']['online'] is True

    def test_merge_discovered_nodes_existing_node(self):
        """Test merging when an existing node is rediscovered."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.listener = CuemsAvahiListener(ip='169.254.1.1')

        # Add existing node to network_map
        existing_node = Node(
            uuid='existing-uuid',
            mac='existingmac12',
            name='existing_node',
            node_role=NodeRole.node,
            ip='192.168.1.10',
            adopted=True,
            online=False,
        )
        nodeconf.network_map['existingmac12'] = existing_node

        # Rediscover the node
        rediscovered_node = Node(
            uuid='existing-uuid',
            mac='existingmac12',
            name='existing_node',
            node_role=NodeRole.node,
            ip='192.168.1.11',  # IP changed
            online=True,
        )
        nodeconf.listener.nodes['existingmac12'] = rediscovered_node

        nodeconf.merge_discovered_nodes()

        # Adopted status should be preserved
        assert nodeconf.network_map['existingmac12']['adopted'] is True
        # Online status should be updated
        assert nodeconf.network_map['existingmac12']['online'] is True
        # IP should be updated
        assert nodeconf.network_map['existingmac12']['ip'] == '192.168.1.11'

    def test_merge_discovered_nodes_offline(self):
        """Test that nodes not discovered are marked offline."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.listener = CuemsAvahiListener(ip='169.254.1.1')

        # Add node to network_map but not to discovered nodes
        offline_node = Node(
            uuid='offline-uuid',
            mac='offlinemac123',
            name='offline_node',
            node_role=NodeRole.node,
            ip='192.168.1.10',
            online=True,
        )
        nodeconf.network_map['offlinemac123'] = offline_node

        nodeconf.merge_discovered_nodes()

        assert nodeconf.network_map['offlinemac123']['online'] is False

    def test_set_master_always_adopted(self):
        """Test that controller nodes are always marked as adopted."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.is_first_run = False

        # Add controller and node nodes
        controller_node = Node(
            uuid='controller-uuid',
            mac='mastermac123',
            name='controller_node',
            node_role=NodeRole.controller,
            ip='192.168.1.1',
            adopted=False,
        )
        plain_node = Node(
            uuid='node-uuid',
            mac='slavemac1234',
            name='node',
            node_role=NodeRole.node,
            ip='192.168.1.2',
            adopted=False,
        )
        nodeconf.network_map['mastermac123'] = controller_node
        nodeconf.network_map['slavemac1234'] = plain_node

        nodeconf.set_master_always_adopted()

        assert nodeconf.network_map['mastermac123']['adopted'] is True
        # Plain node should remain False (not first run)
        assert nodeconf.network_map['slavemac1234']['adopted'] is False

    def test_set_master_always_adopted_first_run(self):
        """Test that on first run, non-controller nodes are not adopted."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.is_first_run = True

        # Add controller and node nodes
        controller_node = Node(
            uuid='controller-uuid',
            mac='mastermac123',
            name='controller_node',
            node_role=NodeRole.controller,
            ip='192.168.1.1',
            adopted=True,  # Was adopted
        )
        plain_node = Node(
            uuid='node-uuid',
            mac='slavemac1234',
            name='node',
            node_role=NodeRole.node,
            ip='192.168.1.2',
            adopted=True,  # Was adopted
        )
        nodeconf.network_map['mastermac123'] = controller_node
        nodeconf.network_map['slavemac1234'] = plain_node

        nodeconf.set_master_always_adopted()

        assert nodeconf.network_map['mastermac123']['adopted'] is True
        # On first run, non-controllers should be False
        assert nodeconf.network_map['slavemac1234']['adopted'] is False
