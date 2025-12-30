"""
Custom XML builders and parsers for node_list and node classes.
These must be imported before using XmlWriter/XmlReader to register them.
"""

from xml.etree.ElementTree import SubElement
import cuemsutils.xml.XmlBuilder as XmlBuilderModule
from cuemsutils.xml.XmlBuilder import CuemsScriptXmlBuilder, GenericCueXmlBuilder, VALUE_TYPES
import cuemsutils.xml.Parsers as ParsersModule
from cuemsutils.xml.Parsers import GenericDict, GenericParser
from cuemsutils.log import Logger


class node_listXmlBuilder(CuemsScriptXmlBuilder):
    """Custom builder for node_list class"""
    def build(self):
        cue_element = SubElement(self.xml_tree, 'node_list')
        for value in self._object.values():
            # Get builder for each node
            builder_class = self.get_builder_class(value)
            sub_object_element = builder_class(value, xml_tree = cue_element).build()
        return self.xml_tree


class nodeXmlBuilder(GenericCueXmlBuilder):
    """Custom builder for node class"""
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


# Custom Parsers for reading XML
class node_listParser(GenericParser):
    """Custom parser for node_list class"""
    def parse(self):
        Logger.debug(f"Parsing node_list with node_listParser")
        self.item_gp = list()
        # init_dict should contain a list of node dictionaries
        for item in self.init_dict:
            for dict_key, dict_value in item.items():
                # Parse each node
                parser_class, class_string = self.get_parser_class(dict_key)
                self.item_gp.append(parser_class(init_dict=dict_value, class_string=class_string).parse())
        return self.item_gp


class nodeParser(GenericParser):
    """Custom parser for node class"""  
    def parse(self):
        Logger.debug(f"Parsing node with nodeParser")
        # Create the node object and populate it
        for dict_key, dict_value in self.init_dict.items():
            if isinstance(dict_value, dict):
                if len(list(dict_value)) > 0:
                    parser_class, class_string = self.get_parser_class(dict_key)
                    self.item_gp[dict_key] = parser_class(init_dict=dict_value, class_string=class_string).parse()
            else:
                dict_value = self.str_to_value(dict_value)
                self.item_gp[dict_key] = dict_value
        return self.item_gp


# Register builders in the XmlBuilder module's globals so they can be found
XmlBuilderModule.node_listXmlBuilder = node_listXmlBuilder
XmlBuilderModule.nodeXmlBuilder = nodeXmlBuilder

# Register parsers in the Parsers module's globals so they can be found
ParsersModule.node_listParser = node_listParser
ParsersModule.nodeParser = nodeParser

