"""
	Extraction utilities and supporting functions

	Some operations are used frequently or repeated enough to be factored out.
	
	Note that SQL can be used via the POORSQL_BINARY_PATH
	  Download the binary from http://architectshack.com/PoorMansTSqlFormatter.ashx
	  It's a phenominal utility that brilliantly normalizes SQL code.
	  Have friends/coworkers/peers who missed an indent? This will prevent
	  a diff utility from tripping up on that.
"""
from shared.tools.yaml.core import dump 

from java.util import Date


# Taken from the Metatools library, copied here for convenience
def getDesignerContext(anchor=None):
	"""Attempts to grab the Ignition designer context.
	This is most easily done with a Vision object, like a window.
	If no object is provided as a starting point, it will attempt to 
	  get one from the designer context.
	"""
	from com.inductiveautomation.ignition.designer import IgnitionDesigner

	if anchor is None:
		
		try:
			return IgnitionDesigner.getFrame().getContext()
		except:
			for windowName in system.gui.getWindowNames():
				try:
					anchor = system.gui.getWindow(windowName)
					break
				except:
					pass
			else:
				raise LookupError("No open windows were found, so no context was derived by default.")
			
	try:
		anchor = anchor.source
	except AttributeError:
		pass
		# Just making sure we've a live object in the tree, not just an event object
		
	for i in range(50):
		if anchor.parent is None: 
			break
		else:
			anchor = anchor.parent
			
		if isinstance(anchor,IgnitionDesigner):
			break
	else:
		raise RuntimeError("No Designer Context found in this object's heirarchy")
		
	context = anchor.getContext()
	return context


POORSQL_BINARY_PATH = 'C:/Workspace/bin/SqlFormatter.exe'
		
# from https://stackoverflow.com/a/165662/13229100
from subprocess import Popen, PIPE, STDOUT

def format_sql(raw_sql):
	"""Normalize the SQL so it is consistent for diffing"""
	try:
		raise KeyboardInterrupt
		
		poorsql = Popen(
			[POORSQL_BINARY_PATH,
			], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
			
		formatted = poorsql.communicate(input=raw_sql)[0]

		return formatted.replace('\r\n', '\n').strip()
	except:
		return raw_sql



import java.awt.Point, java.awt.Dimension, java.util.UUID

BASE_TYPES = set([bool, float, int, long, None, str, unicode])

COERSION_MAP = {
	java.awt.Point: lambda v: {'x': v.getX(), 'y': v.getY()},
	java.awt.Dimension: lambda v: {'width': v.getWidth(), 'height': v.getHeight()},
	java.util.UUID: lambda v: str(v),
	}


def coerceValue(value, default=str):
	if type(value) in BASE_TYPES:
		return value
	else:
		return COERSION_MAP.get(type(value), default)(value)


#ptd = propsetToDict = lambda ps: dict([(p.getName(), ps.get(p)) for p in ps.getProperties()])

def propsetToDict(property_set, recurse=False, coersion=coerceValue, visited=None):
	if visited is None: 
		visited = set()
	elif property_set in visited:
		return None
	
	result_dict = {}
	for prop in property_set.getProperties():
		value = property_set.get(prop)
		
		if recurse and not type(value) in BASE_TYPES:
			try:
				deep = propsetToDict(value, recurse, coersion, visited)
			except:
				try:
					deep = []
					for element in value:
						try:
							deep.append(propsetToDict(element, recurse, coersion, visited))
						except:
							deep.append(coersion(element))
				except:
					deep = None
			
			if deep:
				value = deep
			else:
				value = coersion(value)			
		else:
			value = coersion(value)
		
		result_dict[prop.getName()] = value
	
	return result_dict


def hashmapToDict(hashmap):
	return dict(
		(key, hashmap.get(key))
		for key in hashmap.keySet()
		)


def serializeToXML(obj, context=None):
	if context is None:
		context = getDesignerContext()
	serializer = context.createSerializer()
	serializer.addObject(obj)
	return serializer.serializeXML()
	

def stringify(obj):
	if isinstance(obj, (str, unicode)):
		return str(obj).replace('\r\n', '\n')
	elif isinstance(obj, (list, tuple)):
		return [stringify(item) for item in obj]
	elif isinstance(obj, dict):
		return dict((str(key),stringify(value)) 
					for key, value 
					in obj.items())
	elif isinstance(obj, Date):
		return str(obj.toInstant()) # get the ISO8601 format
	# coerce java and other objects
	elif not isinstance(obj, (int, float, bool)):
		return repr(obj)
	return obj


def yamlEncode(obj):
	return dump(stringify(obj), sort_keys=True, indent=4)


def encode(obj):
	"""
	Encodes object in a serializing format. 
	Returns tuple of serialization format's file extention and the serialized data.
	"""
	return '.yaml', yamlEncode(obj),
#	return '.json', system.util.jsonEncode(obj, 2),



from com.inductiveautomation.ignition.common.xmlserialization import SerializationException
		
def getSerializationCauses(exception):
	"""Many objects may not be able to deserialize if imported from an 
	  Ignition instance with additional (but locally missing) modules.
	
	This will drag out some of the context in an easier to scan way.
	"""
	causes = []
	while exception:
		causes.append(exception)
		exception = exception.getCause()
	return causes
	