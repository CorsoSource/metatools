"""
	Plonk objects to disk!
"""


import array.array, base64, os, re
from shared.corso.meta import getDesignerContext


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['serializeToXML', 'getResources', 'dumpProject']


def serializeToXML(obj, anchor=None):
	serializer = getSerializer(anchor)
	serializer.addObject(obj)
	return serializer.serializeXML()

def getDeserializer(anchor = None):
	context = getDesignerContext(anchor)
	return context.createDeserializer()

def getSerializer(anchor = None):
	context = getDesignerContext(anchor)
	return context.createSerializer()
	

def resolveToObject(objBinary, failsafe=5):
	if not failsafe:
		return NotImplemented
	objects = []
	
	deserializerContext = getDeserializer().deserialize(objBinary)
	rootObjects = deserializerContext.getRootObjects()
	
	for obj in rootObjects:
		if isinstance(obj, (str, unicode)):
			objects.append(obj)
		elif str(type(obj)).startswith("<type 'com.inductiveautomation.factorypmi.application.model"):
			if 'getSerializedBytes' in dir(obj):
				objects.extend(resolveToObject(obj.getSerializedBytes(), failsafe-1))
			elif 'getSerializedCode' in dir(obj):
				objects.extend(resolveToObject(obj.getSerializedCode(), failsafe-1))
			else:
				pass #???!
		else:
			objects.append(obj)
	return objects


def getResources(resourcePattern = '.*', anchor=None):
	"""Given a resource path, this will return the human-readable
	text XML version of that resource.
	
	Args:
	  - resourcePath (str): The resource to return. Returns all in project if falsy.
	  - anchor (object):    An object that is a part of the designer. Used to backtrace the context.
	"""	
	context = getDesignerContext(anchor)
	
	proj = context.getProject()
	
	if resourcePattern:
		rePattern = re.compile(resourcePattern)
		resources = [res for res in proj.getResources() if rePattern.match(str(res.getResourcePath()))]
	else:
		resources = [res for res in proj.getResources()]
	
	resourceData = {}
	errors = []
	for resource in resources:
		if resource is None:
			continue # no data retrieved...
			
		for dataKey in resource.getDataKeys():
			
			resDataKey = '%s--%s' % (resource.resourcePath, dataKey)
			resData = resource.getData(dataKey)
			
			if dataKey.endswith('.py'):
				resourceData[resDataKey] = [''.join([chr(c) for c in resData])]
			elif all((dataKey.endswith('bin'), 
					isinstance(resData, array.array), 
					resData.typecode == 'b')):
				try:
					objs = resolveToObject(resData)
					resourceData[resDataKey] = [obj for obj in objs if not obj is NotImplemented]
				except SerializationException:
					errors.append(resDataKey)
			else:
				resourceData[resDataKey] = [base64.b64encode(resData)]
	
	if errors:
		print 'Errors with de/serialization:\n%s' % '\n'.join(errors)
	
	return resourceData


def dumpProject(dumpDir):

	resourceData = getResources()
	for dataKey,objects in resourceData.items():
		for i,obj in enumerate(objects):
			
			name,_,dataSig = dataKey.rpartition('--')
			dataType,_,dataExt = dataSig.rpartition('.')
			if dataExt == 'bin': 
				dumpString = serializeToXML(obj)
				dataExt = 'xml'
			else:
				dumpString = obj
		
			if i:
				filepath = '%s/%s_%d.%s' % (dumpDir, name, i, dataExt)
			else:
				filepath = '%s/%s.%s' % (dumpDir, name, dataExt)
			
			if os.path.exists(filepath):
				if i:
					filepath = '%s/%s_%d.%s' % (dumpDir, dataKey, i, dataExt)
				else:
					filepath = '%s/%s.%s' % (dumpDir, dataKey, dataExt)
					
			try:
				os.makedirs(filepath.rpartition('/')[0])
			except OSError:
				pass
				
			with open(filepath, 'w') as f:			
				f.write(dumpString)