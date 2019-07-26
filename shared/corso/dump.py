"""
	Plonk objects to disk!
"""

import array.array, base64
from shared.corso.meta import getDesignerContext


__all__ = ['getResourceXML']


def getResourceXML(resourcePath = None, anchor=None):
	"""Given a resource path, this will return the human-readable
	text XML version of that resource.
	
	Args:
	  - resourcePath (str): The resource to return. Returns all in project if falsy.
	  - anchor (object):    An object that is a part of the designer. Used to backtrace the context.
	"""
	if anchor is None:
		anchor = system.gui.getWindow(system.gui.getWindowNames()[0])
	
	context = getDesignerContext(anchor)
	
	deserializer = context.createDeserializer()
	serializer = context.createSerializer()
	
	proj = context.getProject()
	
	if resourcePath:	
		resources = [proj.getResource(resourcePath).get()]
	else:
		resources = [res.get() for res in proj.getResources()]
	
	resourceData = {}
	for resource in resources:
		if resource is None:
			continue # no data retrieved...
			
		for dataKey in resource.getDataKeys():
			
			resDataKey = '%s :: %s' % (resource.resourcePath, dataKey)
			
			resData = resource.getData(dataKey)
			
			if all((dataKey.endswith('bin'), 
					isinstance(resData, array.array), 
					resData.typecode == 'b')):
					
				deserializerContext = deserializer.deserialize(resData)
				rootObjects = deserializerContext.getRootObjects()

				resourceData[resDataKey] = [ro for ro in rootObjects]
		
				for ro in rootObjects:
					serializer.addObject(ro)
			else:
				resourceData[resDataKey] = base64.b64encode(resData)
				
	xmlOut = serializer.serializeXML()
	
	return xmlOut