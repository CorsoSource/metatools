"""
	Vision windows and templates

	Windows and templates are dumped to disk as raw XML. This is a complete and total
	  definition of the resource and can be used to determine micro-changes.
	  Due to how the serializer may optimize the output, though, ordering and 
	  micro-changes in component configuations can throw diff utilities off severely.
	Either parse the XML directly and compare ordered XML trees for proper diffing,
	  or traverse the window/template objects to get only the information of interest.
	
	TODO: Allow for non-XML dumps using only attributes of interest.
"""

from shared.tools.snapshot.utils import getSerializationCauses, serializeToXML


def extract_window(resource_objects, deserializer=None):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'
	
	window_info = resource_objects[0]
	
	try:
		window_context = deserializer.deserializeBinary(window_info.getSerializedCode())
	except SerializationException, error:	
		return {
			'.error': '\n'.join([str(e) for e in getSerializationCauses(error)])
			}
	
	window = window_context.getRootObjects()[0]
	
	return {
		'.xml': serializeToXML(window)
		}
		

def extract_template(resource_objects, deserializer=None):
	assert len(resource_objects) == 1, 'Resource is expected to be contained in one root object'

	template_info = resource_objects[0]
	
	try:
		template_context = deserializer.deserializeBinary(template_info.getSerializedBytes())
	except SerializationException, error:	
		return {
			'.error': '\n'.join([str(e) for e in getSerializationCauses(error)])
			}
	
	template = template_context.getRootObjects()[0]
	
	return {
		'.xml': serializeToXML(template)
		}


# Ready for the dispatcher
EXTRACTORS = {
	             'window': extract_window,
	 'component-template': extract_template,
	}
