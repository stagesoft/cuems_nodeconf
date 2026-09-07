"""
Tests for engine callback functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
from cuemsnodeconf.CuemsNodeConf import CuemsNodeConf
from cuemsutils.tools.NodeList import NodeIndex, NodeRole, node as Node


class TestEngineCallback:
    """Test engine callback functionality."""

    def test_engine_callback_adopt_node(self, tmp_path, monkeypatch):
        """Test engine callback for adopting a node."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.map_path = str(tmp_path / 'network_map.xml')

        # Add a node to network_map
        node = Node(
            uuid='test-uuid-123',
            mac='testmac123456',
            name='test_node',
            node_role=NodeRole.node,
            ip='192.168.1.10',
            adopted=False,
        )
        nodeconf.network_map['testmac123456'] = node
        
        # Create mock context
        mock_context = MagicMock()
        mock_context.asend = MagicMock()
        
        # Create communications thread mock
        nodeconf.communications_thread = MagicMock()
        nodeconf.communications_thread.event_loop = MagicMock()
        nodeconf.communications_thread.respond_to_engine = MagicMock()
        
        message = {
            'action': 'nodelist_modify',
            'value': 'test-uuid-123',
            'modify_action': 'ADD'
        }
        
        with patch.object(nodeconf, 'adopt_node', return_value={'OK': True}) as mock_adopt, \
             patch('asyncio.run_coroutine_threadsafe'):
            
            nodeconf.engine_callback(message, mock_context)
            
            mock_adopt.assert_called_once_with('test-uuid-123')
    
    def test_engine_callback_unadopt_node(self, tmp_path, monkeypatch):
        """Test engine callback for unadopting a node."""
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.map_path = str(tmp_path / 'network_map.xml')

        # Create mock context and thread
        mock_context = MagicMock()
        nodeconf.communications_thread = MagicMock()
        nodeconf.communications_thread.event_loop = MagicMock()
        nodeconf.communications_thread.respond_to_engine = MagicMock()
        
        message = {
            'action': 'nodelist_modify',
            'value': 'test-uuid-123',
            'modify_action': 'REMOVE'
        }
        
        with patch.object(nodeconf, 'unadopt_node', return_value={'OK': True}) as mock_unadopt, \
             patch('asyncio.run_coroutine_threadsafe'):
            
            nodeconf.engine_callback(message, mock_context)
            
            mock_unadopt.assert_called_once_with('test-uuid-123')
    
    def test_engine_callback_invalid_action(self):
        """Test engine callback with invalid modify_action."""
        nodeconf = CuemsNodeConf()
        
        # Create mock context and thread
        mock_context = MagicMock()
        nodeconf.communications_thread = MagicMock()
        nodeconf.communications_thread.event_loop = MagicMock()
        nodeconf.communications_thread.respond_to_engine = MagicMock()
        
        message = {
            'action': 'nodelist_modify',
            'value': 'test-uuid-123',
            'modify_action': 'INVALID'
        }
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            nodeconf.engine_callback(message, mock_context)
            
            # Should call respond_to_engine with error
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            # The coroutine should send an error response
            assert call_args is not None
    
    def test_engine_callback_exception_handling(self):
        """Test that exceptions in engine_callback are handled gracefully."""
        nodeconf = CuemsNodeConf()
        
        # Create mock context and thread
        mock_context = MagicMock()
        nodeconf.communications_thread = MagicMock()
        nodeconf.communications_thread.event_loop = MagicMock()
        nodeconf.communications_thread.respond_to_engine = MagicMock()
        
        message = {
            'action': 'nodelist_modify',
            'value': 'test-uuid-123',
            'modify_action': 'ADD'
        }
        
        # Make adopt_node raise an exception
        with patch.object(nodeconf, 'adopt_node', side_effect=Exception("Test error")), \
             patch('asyncio.run_coroutine_threadsafe') as mock_run:
            
            # Should not raise, but handle the exception
            nodeconf.engine_callback(message, mock_context)
            
            # Should still call respond_to_engine with error response
            assert mock_run.called



class TestEveryRequestGetsAnAnswer:
    """A Req/Rep socket must never be left hanging.

    Before the else-branch in engine_callback, a well-formed message carrying
    any action other than 'nodelist_modify' returned without responding. The
    engine then blocked on its own 15 s IPC timeout and the operator saw an
    unexplained stall with nothing in either log to explain it.
    """

    def _nodeconf(self):
        nodeconf = CuemsNodeConf()
        nodeconf.network_map = NodeIndex()
        nodeconf.communications_thread = MagicMock()
        nodeconf.communications_thread.event_loop = MagicMock()
        nodeconf.communications_thread.respond_to_engine = MagicMock()
        return nodeconf

    def test_unknown_action_is_answered(self):
        nodeconf = self._nodeconf()
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            nodeconf.engine_callback({'action': 'nodeconf'}, MagicMock())

        assert mock_run.called, 'unknown action must still get a reply'
        response = nodeconf.communications_thread.respond_to_engine.call_args[0][0]
        assert response['OK'] is False
        assert 'unknown action' in response['error']
        assert 'nodeconf' in response['error']

    def test_missing_action_is_answered(self):
        nodeconf = self._nodeconf()
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            nodeconf.engine_callback({'value': 'whatever'}, MagicMock())

        assert mock_run.called
        response = nodeconf.communications_thread.respond_to_engine.call_args[0][0]
        assert response['OK'] is False
        assert 'unknown action' in response['error']

    def test_non_dict_message_is_answered(self):
        """The editor's legacy `nodeconf` action arrives as a bare '' string."""
        nodeconf = self._nodeconf()
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            nodeconf.engine_callback('', MagicMock())

        assert mock_run.called
        response = nodeconf.communications_thread.respond_to_engine.call_args[0][0]
        assert response['OK'] is False
