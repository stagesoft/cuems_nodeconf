#!/usr/bin/env python3
"""
Test XML serialization/deserialization with node_list and node classes.
This simulates what happens in the actual service.
"""

import sys
import os
import tempfile

# Add cuemsnodeconf to path to test as it would be imported from the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cuemsnodeconf'))

# Import classes first
from CuemsNode import CuemsNode, CuemsNodeDict, node, node_list

# Now manually register the builders and parsers (simulating what NodeXmlBuilders does)
from xml.etree.ElementTree import SubElement
import cuemsutils.xml.XmlBuilder as XmlBuilderModule
from cuemsutils.xml.XmlBuilder import CuemsScriptXmlBuilder, GenericCueXmlBuilder, VALUE_TYPES
import cuemsutils.xml.Parsers as ParsersModule
from cuemsutils.xml.Parsers import GenericDict, GenericParser
from cuemsutils.xml.XmlReaderWriter import XmlReader, XmlWriter
from cuemsutils.log import Logger

# Define and register builders
class node_listXmlBuilder(CuemsScriptXmlBuilder):
    def build(self):
        cue_element = SubElement(self.xml_tree, 'node_list')
        for value in self._object.values():
            builder_class = self.get_builder_class(value)
            sub_object_element = builder_class(value, xml_tree = cue_element).build()
        return self.xml_tree

class nodeXmlBuilder(GenericCueXmlBuilder):
    def build(self):
        cue_element = SubElement(self.xml_tree, 'node')
        for key, value in self._object.items():
            if isinstance(value, VALUE_TYPES):
                cue_subelement = SubElement(cue_element, str(key))
                cue_subelement.text = str(value)
            elif isinstance(value, (type(None))):
                cue_subelement = SubElement(cue_element, str(key))
            elif isinstance(value, list):
                cue_subelement = SubElement(cue_element, str(key))
                for list_item in value:
                    builder_class = self.get_builder_class(list_item)
                    sub_object_element = builder_class(list_item, xml_tree = cue_subelement).build()
            elif isinstance(value, GenericDict):
                cue_subelement = SubElement(cue_element, str(key))
                for sub_key, sub_value in value.items():
                    sub_dict_element = SubElement(cue_subelement, str(sub_key))
                    sub_dict_element.text = str(sub_value)
            else:
                cue_subelement = SubElement(cue_element, str(key))
                builder_class = self.get_builder_class(value)
                sub_object_element = builder_class(value, xml_tree = cue_subelement).build()
        return self.xml_tree

# Define and register parsers
class node_listParser(GenericParser):
    def __init__(self, init_dict, class_string):
        self.init_dict = init_dict
        self.class_string = class_string
        self._class = node_list
        self.item_gp = list()
    
    def parse(self):
        Logger.debug(f"Parsing node_list with node_listParser")
        for item in self.init_dict:
            for dict_key, dict_value in item.items():
                parser_class, class_string = self.get_parser_class(dict_key)
                self.item_gp.append(parser_class(init_dict=dict_value, class_string=class_string).parse())
        return self.item_gp

class nodeParser(GenericParser):
    def __init__(self, init_dict, class_string):
        self.init_dict = init_dict
        self.class_string = class_string
        self._class = node
        self.item_gp = node()
    
    def parse(self):
        Logger.debug(f"Parsing node with nodeParser")
        for dict_key, dict_value in self.init_dict.items():
            if isinstance(dict_value, dict):
                if len(list(dict_value)) > 0:
                    parser_class, class_string = self.get_parser_class(dict_key)
                    self.item_gp[dict_key] = parser_class(init_dict=dict_value, class_string=class_string).parse()
            else:
                dict_value = self.str_to_value(dict_value)
                self.item_gp[dict_key] = dict_value
        return self.item_gp

# Register them
XmlBuilderModule.node_listXmlBuilder = node_listXmlBuilder
XmlBuilderModule.nodeXmlBuilder = nodeXmlBuilder
ParsersModule.node_listParser = node_listParser
ParsersModule.nodeParser = nodeParser

import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def test_xml_roundtrip():
    """Test writing and reading back node data"""
    
    # Create test data using the classes
    test_map = CuemsNodeDict()
    
    test_node = CuemsNode({
        'uuid': 'test-uuid-1234-5678',
        'mac': '00e04c01b7e3',
        'name': 'test-node._cuems_nodeconf._tcp.local.',
        'node_type': 'master',
        'ip': '169.254.9.194',
        'adopted': True,
        'online': True
    })
    
    test_map['00e04c01b7e3'] = test_node
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as xml_file:
        xml_path = xml_file.name
    
    xsd_path = os.path.join(os.path.dirname(__file__), 'cuemsnodeconf', 'network_map.xsd')
    
    try:
        # Test 1: Write XML
        print("\n=== TEST 1: Writing XML ===")
        print(f"Writing test data: {dict(test_node)}")
        
        writer = XmlWriter(schema_name=xsd_path, xmlfile=xml_path, xml_root_tag='CuemsNetworkMap')
        writer.write_from_object(test_map)
        print("✅ XML written successfully")
        
        # Show the XML
        with open(xml_path, 'r') as f:
            xml_content = f.read()
            print("\nGenerated XML:")
            print(xml_content)
        
        # Test 2: Read XML back
        print("\n=== TEST 2: Reading XML ===")
        reader = XmlReader(schema_name=xsd_path, xmlfile=xml_path)
        nodes = reader.read_to_objects()
        
        print(f"Read {len(nodes)} nodes")
        
        # Test 3: Validate the data
        print("\n=== TEST 3: Validating parsed data ===")
        for node_data in nodes:
            print(f"Parsed node type: {type(node_data)}")
            print(f"Parsed node data: {node_data}")
            
            # Check if it's a proper node object (has mac attribute)
            if hasattr(node_data, 'mac'):
                print(f"✅ Node has 'mac' attribute: {node_data.mac}")
            else:
                print(f"❌ ERROR: Node object has no 'mac' attribute!")
                print(f"   Type: {type(node_data)}")
                print(f"   Available attributes: {dir(node_data)}")
                return False
            
            # Verify all required fields
            required_fields = ['uuid', 'mac', 'name', 'node_type', 'ip', 'adopted', 'online']
            for field in required_fields:
                if field in node_data:
                    print(f"  ✅ {field}: {node_data[field]}")
                else:
                    print(f"  ❌ Missing field: {field}")
                    return False
        
        print("\n🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if os.path.exists(xml_path):
            os.unlink(xml_path)

if __name__ == '__main__':
    success = test_xml_roundtrip()
    sys.exit(0 if success else 1)

