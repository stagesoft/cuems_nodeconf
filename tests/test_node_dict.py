"""
Tests for NodeIndex role selections (controllers, by_role(node), by_role(firstrun)).

feature 007: ``CuemsNodeDict``'s ``masters``/``slaves``/``firstruns``
properties do not migrate — they named a vocabulary that no longer exists.
``cuemsutils.tools.NodeList.NodeIndex`` replaces them with ``.controllers``
and the general ``.by_role(NodeRole)`` selector.
"""
import pytest
from cuemsutils.tools.NodeList import NodeIndex, NodeRole, node as Node


class TestNodeIndexRoleSelections:
    """Test NodeIndex role selections (controllers, by_role)."""

    def test_node_index_controllers_property(self):
        """Test that controllers property returns only controller nodes."""
        node_index = NodeIndex()

        controller = Node(
            uuid='controller-uuid',
            mac='mastermac123',
            name='controller',
            node_role=NodeRole.controller,
            ip='192.168.1.1',
        )
        plain = Node(
            uuid='node-uuid',
            mac='slavemac1234',
            name='node',
            node_role=NodeRole.node,
            ip='192.168.1.2',
        )

        node_index['mastermac123'] = controller
        node_index['slavemac1234'] = plain

        controllers = node_index.controllers
        assert len(controllers) == 1
        assert controllers[0]['node_role'] == NodeRole.controller

    def test_node_index_by_role_node(self):
        """Test that by_role(NodeRole.node) returns only plain nodes."""
        node_index = NodeIndex()

        controller = Node(
            uuid='controller-uuid',
            mac='mastermac123',
            name='controller',
            node_role=NodeRole.controller,
            ip='192.168.1.1',
        )
        plain = Node(
            uuid='node-uuid',
            mac='slavemac1234',
            name='node',
            node_role=NodeRole.node,
            ip='192.168.1.2',
        )

        node_index['mastermac123'] = controller
        node_index['slavemac1234'] = plain

        nodes = node_index.by_role(NodeRole.node)
        assert len(nodes) == 1
        assert nodes[0]['node_role'] == NodeRole.node

    def test_node_index_by_role_firstrun(self):
        """Test that by_role(NodeRole.firstrun) returns only firstrun nodes."""
        node_index = NodeIndex()

        firstrun = Node(
            uuid='firstrun-uuid',
            mac='firstrunmac12',
            name='firstrun',
            node_role=NodeRole.firstrun,
            ip='192.168.1.3',
        )
        plain = Node(
            uuid='node-uuid',
            mac='slavemac1234',
            name='node',
            node_role=NodeRole.node,
            ip='192.168.1.2',
        )

        node_index['firstrunmac12'] = firstrun
        node_index['slavemac1234'] = plain

        firstruns = node_index.by_role(NodeRole.firstrun)
        assert len(firstruns) == 1
        assert firstruns[0]['node_role'] == NodeRole.firstrun
