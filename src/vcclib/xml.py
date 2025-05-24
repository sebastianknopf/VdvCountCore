from lxml import etree

def _build_xml_element(parent, d, attribute_mapping=None):
    
    if attribute_mapping is None:
        attribute_mapping = {}

    if isinstance(d, dict):
        attrib_keys = attribute_mapping.get(parent.tag, set())
        attrib = {}
        content = {}

        for key, value in d.items():
            if key in attrib_keys:
                attrib[key] = str(value)
            else:
                content[key] = value

        parent.attrib.update(attrib)

        for key, value in content.items():
            if isinstance(value, list):
                for item in value:
                    child = etree.SubElement(parent, key)
                    _build_xml_element(child, item, attribute_mapping)
            else:
                child = etree.SubElement(parent, key)
                _build_xml_element(child, value, attribute_mapping)
    else:
        parent.text = str(d)

def dict2xml(tag, d, attribute_mapping=None) -> str:
    root = etree.Element(tag)
    _build_xml_element(root, d, attribute_mapping)

    etree.indent(root, space="    ")
    xml_str: str = etree.tostring(root, pretty_print=True)

    return xml_str
