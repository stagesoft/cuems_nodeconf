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

