"""
	A handy set of pretty printers for dumping info in Ignition.

	These are meant to be used with a console.
"""


import __builtin__
import re, math, textwrap
from types import *
from array import array
from java.util import ArrayList, HashSet, HashMap, Collections
from java.lang import Exception as JavaException

import java.lang.Class as JavaClass
from com.inductiveautomation.ignition.common import BasicDataset
from com.inductiveautomation.ignition.common.script.builtin.DatasetUtilities import PyDataSet
from shared.tools.meta import getObjectName, getFunctionCallSigs, sentinel, isJavaObject, getReflectedField


class PrettyException(Exception):
	def __repr__(self):
		return 'PrettyPrinter failed: %r' % self.message


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['p','pdir']


quotePattern = re.compile("""^('.*'|".*")$""")

PRETTY_PRINT_TYPES = (BasicDataset, PyDataSet, 
					  list, tuple, array, ArrayList, Collections, 
					  dict, HashMap,
					  set, frozenset, HashSet,
					  FrameType, FunctionType, LambdaType)
IGNORED_NAMES = set(['o', 'obj', 'element', 'attr', 'val', 'function'])


def repr_function(function, estimatedDepth=1):
	f_name = getObjectName(function,estimatedDepth=estimatedDepth, ignore_names=IGNORED_NAMES)
	return '%s%s' % (f_name or 'λ', getFunctionCallSigs(function))


def pdir(o, indent='  ', ellipsisLimit=120, includeDocs=False, skipPrivate=True, recurseSkips=set(), recursePrettily=False, directPrint=True):
	"""Pretty print the dir() function for Ignition things. This is designed to be used in the 
	  script console. Use it to explore objects and functions.

	Functions will show their call methods, with Python functions returning their defaults, if any.
	Attributes that are objects will be printed directly, and otherwise the type will be displayed.

	Disable direct print if the output of the function should be returned for use elsewhere
	  (perhaps to a file or something).

	When in doubt, pdir(pdir) is a handy thing to remember. Or help(pdir), too!
	"""
	# skipTypes = set(['builtin_function_or_method', 'instancemethod', 'java.lang.Class'])
	skipTypes = set(['builtin_function_or_method', 'java.lang.Class'])
		
	dotdotdot = lambda s,ellipsisLimit=ellipsisLimit: s if not ellipsisLimit or len(s)<=ellipsisLimit else '%s...' % s[:ellipsisLimit-3]
	
	out = []	
	
	name = getObjectName(o,estimatedDepth=2, ignore_names=IGNORED_NAMES)
	if name:
		out += ['%sProperties of "%s" <%s>' % (indent, name, str(type(o))[6:-1])]
	else:
		out += ['%sProperties of <%s>' % (indent, str(type(o))[6:-1])]
	out += ['%s%s' % (indent, '='*len(out[0]))]
	
	obj_repr = repr(o)
	if obj_repr:
		obj_repr = obj_repr.splitlines() if '\n' in obj_repr else [obj_repr]
		
		for line in obj_repr:
			out += ['%s%s' % (indent, dotdotdot(line))]
		out += ['%s%s' % (indent, '-'*len(out[0]))]

	try:
		joinClause = '\n---\n'
		callExample = '%s%s' % (indent, getFunctionCallSigs(o, joinClause),)
		out += callExample.split(joinClause)
		out += ['%s%s' % (indent, '-'*max([len(line) for line in callExample.split(joinClause)] + [1]))]
	except:
		pass
	
	if getattr(o, '__doc__', ''):
		docstringLines = o.__doc__.strip().splitlines()
		if len(docstringLines) > 1:
			docstringLines = [docstringLines[0]] + textwrap.dedent('\n'.join(docstringLines[1:])).splitlines()
		maxDocLen = max([len(line) for line in docstringLines] + [1])
		docPattern = '%%s%%-%ds' % maxDocLen
		for line in docstringLines:
			out += [docPattern % (indent, line)]
		else:
			out += ['']

	attrDir = set(dir(o))
	
	try:
		if isJavaObject(o) and not skipPrivate:
			attributes = set(attr.name for attr in o.getDeclaredFields())
			attributes |= attrDir
		else:
			raise StopIteration("Default to the normal dir command...")		
	except:
		attributes = [attribute for attribute in attrDir
					  if not (attribute.startswith('_') and skipPrivate)]
	
	attributes = sorted(attributes)
	
	# preprocessing
	maxAttrLen = max([len(attribute) 
					  for attribute in attributes] + [0])	
	
	attrTypes = []
	attrTypeStrings = []
	attrReprs = []
	attrPrivates = []
	attrDocs = []
	for attribute in sorted(attributes):
	
		try:
			attrPrivates.append((not attribute in attrDir) or attribute.startswith('_'))
			
			if not attribute in attrDir:
				attrType = o.getDeclaredField(attribute).type
				
				attrTypes.append(attrType)
				typeStr = str(attrType)[7:-2]
				typeStr = typeStr.partition('$')[0]
				attrTypeStrings.append(typeStr)
				
				attrReprs.append(repr(getReflectedField(o,attribute)))
				attrDocs.append(None)
			else:
				try:
					attr = getattr(o,attribute)
					attrType = type(attr)
				except:
				
					attr = PrettyException('could not get attribute %s' % attribute)
					attrType = "<type '<Unknown type>'>"
				
				attrTypes.append(attrType)
				typeStr = str(attrType)[7:-2]
				typeStr = typeStr.partition('$')[0]
				attrTypeStrings.append(typeStr)

				try:
					if recursePrettily and isinstance(attr, PRETTY_PRINT_TYPES) and not attribute in recurseSkips:
						attrReprs.append(p(attr, listLimit=10, ellipsisLimit=ellipsisLimit, nestedListLimit=4, directPrint=False))						
					else:
						if getattr(attr, '__call__', None):
							if re.match('(get|to|is|has)[A-Z]', attribute) and shared.tools.meta.getFunctionCallSigs(attr) == '()':
								attrReprs.append(repr(attr()))
							else:
								attrReprs.append(repr_function(attr))
						else:
							attrReprs.append(repr(attr))
				except:
					try:
						attrReprs.append(str(attr))
					except:
						attrReprs.append('< ? >')
				
				try:
					attrDocs.append(' '.join(attr.__doc__.strip().splitlines()))	
				except:
					attrDocs.append(None)
					
		except AttributeError, e:
			try:
				attr = getattr(o,attribute)
#				print attr
#				print getFunctionCallSigs(attr)
			except:
				pass
			attrTypes.append('<--->')
			attrTypeStrings.append(str(e).partition(':')[0])
			attrReprs.append('n/a')
			attrDocs.append(None)
		except TypeError, e:
			attrTypes.append('WriteOnly')
			attrTypeStrings.append(str(e).partition(':')[0])
			attrReprs.append('n/a')
			attrDocs.append(None)
		except (Exception, JavaException), e: # IllegalComponentStateException
			attrTypes.append('unavailable')
			attrTypeStrings.append(str(e).partition(':')[0])
			attrReprs.append('n/a')
			attrDocs.append(None)
			
	attrReprs = [ar.strip() if not '\n' in ar else ar for ar in attrReprs]
	
	maxTypeLen = 2 + max([len(attrTypeStr) 
						  for attrTypeStr in attrTypeStrings
						  if not attrTypeStr in skipTypes] + [0])
						  
	maxReprLen = max([len(attrRepr.rstrip())+2 if not '\n' in attrRepr else max(len(line.rstrip()) for line in attrRepr.splitlines())
						  for attrTypeStr,attrRepr in zip(attrTypeStrings,attrReprs)
						  if not attrTypeStr in skipTypes] + [0])
						  
	if ellipsisLimit and maxReprLen > ellipsisLimit:
		maxReprLen = ellipsisLimit
						  
	attrPattern    = '%s%%-%ds   %%3s   %%-%ds   %%-%ds'       % (indent, maxAttrLen+3, maxReprLen+3, maxTypeLen+3)
	attrDocPattern = attrPattern + ('   %%-%ds' % ellipsisLimit)

	out += [attrPattern % ('Attribute', '(P)', 'Repr', r'<Type>')]
	out += [attrPattern % ('-'*maxAttrLen, '---', '-'*maxReprLen, '-'*maxTypeLen)]
	
	# calculating
	for attrType,attrPriv,attrTypeStr,attribute,attrRepr,attrDoc in zip(attrTypes,attrPrivates,attrTypeStrings,attributes,attrReprs,attrDocs):
		
		attrPriv = ' * ' if attrPriv else '   '
		
		if attrTypeStr in skipTypes:
			attrTypeStr = ''
			attrRepr = ''
		else:
			attrTypeStr = '%s' % attrTypeStr

		attribute = attribute.strip()
		attrTypeStr =  attrTypeStr.strip()
				
		if not '\n' in attrRepr and not (attrType in (str, unicode) and r'\n' in attrRepr):
			attrRepr = attrRepr.strip()
			attrReprLines = []
			
			attrRepr = dotdotdot(attrRepr, maxReprLen)
				
		else: # this is a multiline string repr
			attrTypeStr = ''
			attrDoc = ''
			if attrType in (str, unicode):
				# get the original string back...
				attrRepr = getattr(o, attribute)
				attrRepr = textwrap.dedent(attrRepr)
				attrReprLines = attrRepr.splitlines()		
			else:
				attrReprLines = attrRepr.splitlines()
			
			attrReprSpacing = len(indent) + 3 + 3 + 3 + maxAttrLen + 2
			attrRepr = attrReprLines.pop(0)
		
		# This is a weird format error I don't care to figure out...
		if attrRepr.startswith('λ('):
			attrTypeStr = ' ' + attrTypeStr
		
		attrTypeStr = dotdotdot(attrTypeStr, maxReprLen)

		if attrDoc and includeDocs:
			outStr = attrDocPattern % (attribute, attrPriv, attrRepr, attrTypeStr, attrDoc)
		else:
			outStr = attrPattern % (attribute, attrPriv, attrRepr, attrTypeStr)
		
		# the repr for the attribute took more than one line, format that in
		if len(attrReprLines) > 0:
			out += [outStr]
			
			for reprLine in attrReprLines:
				out += [' '*attrReprSpacing + dotdotdot(reprLine.rstrip(),maxReprLen)]
		else:
			outStr = ' -- '.join(outStr.splitlines())
			out += [outStr]
	
	out += ['']

	output = '\n'.join(out)
	if directPrint:
		print output
	else:
		return output


def p(o, indent='  ', listLimit=42, ellipsisLimit=80, nestedListLimit=10, directPrint=True):
	"""Pretty print objects. This helps make lists, dicts, and other things easier to understand.
	Handy for quickly looking at datasets and lists of lists, too, since it aligns columns.
	"""
	# Pass-thru for strings
	if isinstance(o, (str, unicode)):
		return o
	
	out = []
	
	strElePattern = '%%-%ds'
	numElePattern = '%%%ds'	
	colSep = ' |  '
	
	if isinstance(o, (BasicDataset,PyDataSet)):
		ds = o
		
		o_name = getObjectName(o,estimatedDepth=2, ignore_names=IGNORED_NAMES)
		o_name = ('"%s" ' % o_name) if o_name else ''
		if isinstance(ds, PyDataSet):
			ds = ds.getUnderlyingDataset()
			out += ['%s<PyDataSet> of %d elements and %d columns' % (o_name, ds.getRowCount(), ds.getColumnCount())]
		else:
			out += ['%s<DataSet> of %d elements and %d columns' % (o_name, ds.getRowCount(), ds.getColumnCount())]
		out += [indent + '='*len(out[0])]
		
		# preprocessing
		# Get the width of each column in the dataset
		try:
			data = zip(*ds.data)
		except AttributeError:
			data = []
			for rix in sentinel(range(ds.getRowCount()),listLimit):
				data.append([ds.getValueAt(rix,cix) for cix in range(ds.getColumnCount())])

		colTypes = [repr(t) for t in ds.getColumnTypes()]
		colTypeStrs = [' <%s> ' % ct[7:-2] for ct in colTypes]
		colNames = [h for h in ds.getColumnNames()]
		
		colWidths = [max([len(repr(row)) for row in col] + [len(t)] + [len(h)] + [1]) 
					 for h,t,col 
					 in zip(colNames,colTypeStrs,zip(*data))]
		
		maxRowWidth = int(math.floor(math.log10(ds.getRowCount())))
		
		prefixPattern =  '%s %%%dd%s' %  (indent, maxRowWidth + 1, colSep)

		rowPattern = prefixPattern + '  ' + colSep.join(strElePattern % colWidth 
													  if colType in ("<type 'java.lang.String'>",repr(str), repr(unicode)) 
													  else numElePattern % colWidth
													  for colType, colWidth in zip(colTypes,colWidths))
		hedPattern = indent + '   ' + ' '*(maxRowWidth+1) + '  ' + '  ' + colSep.join(strElePattern % colWidth
													  for colWidth in colWidths)		
													  
		out += [hedPattern % tuple(colNames)]
		out += [hedPattern % tuple(colTypeStrs)]
		out += [indent + '-'*(len(out[-1])-len(indent))]
		
		for i, row in enumerate(data):
			out += [rowPattern % tuple([i] + list(row))]		
		
		
	elif isinstance(o, (list, tuple, array, ArrayList, set, frozenset, HashSet)):
		o_name = getObjectName(o,estimatedDepth=2, ignore_names=IGNORED_NAMES)
		o_type = type(o)
		
		if isinstance(o, HashSet):
			o = set([v for v in o])
		
		out += ['%s<%s> of %d elements' % (
			('"%s" ' % o_name) if o_name else '', 
		    '<%s> array' % o.typecode if isinstance(o,array) else str(o_type)[6:-1],
			len(o))]
		
		# preprocessing
		maxRowWidth = int(math.floor(math.log10(len(o) + 1)))
		
		# column alignment, if any
		try:
			colEleWidths = [max([len(repr(r)) for r in row] + [1]) for row in zip(*o)]
		except:
			colEleWidths = []
		
		if not colEleWidths:
			colEleWidths = [max([len(repr(element) 
									 if not isinstance(element, PRETTY_PRINT_TYPES) 
									 else '1')
								 for element in o] + [1])]
			
		# element printing
		for i,element in enumerate(o):
			ixPattern = '%%%dd'
			if isinstance(element, (dict, set,frozenset)):
				ixPattern = '{%s}' % ixPattern
			elif isinstance(element, (list,array,ArrayList)):
				ixPattern = '[%s]' % ixPattern
			elif isinstance(element, tuple):
				ixPattern = '(%s)' % ixPattern
			elif isinstance(o, (set,frozenset)):
				ixPattern = ' %s?' % ixPattern
			else:
				ixPattern = ' %s ' % ixPattern
	
			prefixPattern =  '%s' + ixPattern + ' %s'
			prefixPattern %= (indent, maxRowWidth + 1, colSep)

			if isinstance(element, PRETTY_PRINT_TYPES):			
				nestedPattern = '%s' + ixPattern + ' %s%%s'
				nestedPattern %= (indent, maxRowWidth + 1, colSep)
				out += [nestedPattern % (i, p(element,
											  indent+' '*(maxRowWidth+1+2+2+len(colSep)), 
											  listLimit=nestedListLimit,
											  ellipsisLimit=ellipsisLimit,
											  nestedListLimit=nestedListLimit,
											  directPrint=False))]
				out[-1] = out[-1][:-1]
				continue
			
			else:
				rElement = repr(element)
				if ellipsisLimit and len(rElement) > ellipsisLimit:
					if quotePattern.match(rElement):
						rElement = '%s...%s' % (rElement[:ellipsisLimit-4], rElement[0])
					else:
						rElement = '%s...' % rElement[:ellipsisLimit-3]
				
				rowPattern = prefixPattern
				if isinstance(element, (str, unicode)):
					rowPattern += '  ' + strElePattern % colEleWidths[0]
				else:
					rowPattern += '  ' + numElePattern % colEleWidths[0]
				out += [rowPattern % (i, rElement)]
			
			if listLimit and i >= listLimit-1:
				out += ['%s... %d ellided (of %s total)' % (indent, len(o)-i-1, len(o))]
				break
				
	elif isinstance(o, (dict, HashMap)):
		o_name = getObjectName(o,estimatedDepth=2, ignore_names=IGNORED_NAMES)
		o_type = type(o)
		
		if isinstance(o, HashMap):
			o = dict([
				(str(key), o.get(key))
				for key in sorted(o.keySet())
				])
		
		out.append('%s<%s> of %d elements' % (('"%s" ' % o_name) if o_name else '', str(o_type)[6:-1],len(o)))
		
		# preprocessing
		maxKeyWidth = max([len(repr(key)) for key in o.keys()] + [1])
		maxValWidth = max([len(repr(val)
		                       if not isinstance(val, PRETTY_PRINT_TYPES) 
		                       else '1')
		                   for val in o.values()] + [1])
		
		elementPattern = '%s%%%ds : %%-%ds' % (indent, maxKeyWidth, maxValWidth)
		
		# element printing
		for i,key in enumerate(sorted(o.keys())):
			element = o[key]
			
			if isinstance(element, PRETTY_PRINT_TYPES) and element is not o: #don't recurse here!
				nestedPattern = '%s%%%ds : %%s' % (indent, maxKeyWidth)
				out += [nestedPattern % (key, p(element, 
											    indent+' '*(maxKeyWidth+3),
											    listLimit=nestedListLimit, 
											    ellipsisLimit=ellipsisLimit,
											    nestedListLimit=nestedListLimit, 
											    directPrint=False).lstrip())]
				out[-1] = out[-1][:-1]
				continue
			
			rElement = repr(element)
			if ellipsisLimit and len(rElement) > ellipsisLimit:
				if quotePattern.match(rElement):
					rElement = '%s...%s' % (rElement[:ellipsisLimit-4], rElement[0])
				else:
					rElement = '%s...' % rElement[:ellipsisLimit-3]

			out += [elementPattern % (key,rElement)]
						
			if listLimit and i >= listLimit-1:
				out += ['%s... %d ellided (of %s total)' % (indent, len(o)-i-1, len(o))]
				break
		
	elif isinstance(o, FrameType):
		out += ['<frame in "%s" of "%s" on line %d%s>' % (
						o.f_code.co_filename,
						o.f_code.co_name,
						o.f_lineno,
						('(tracing with %s)' % o.f_trace) if o.f_trace else ''
					)]
					
	elif isinstance(o, (FunctionType,LambdaType)):
		out += [repr_function(o, estimatedDepth=1)]
		
	else:
		if not isinstance(o, GeneratorType):
			try: # if it's some sort of unknown iterable
				if directPrint:
					p([v for v in o], indent, listLimit, ellipsisLimit, nestedListLimit, directPrint)
					print '(Unrecognized type - iteration attempted for type <%r>)' % str(type(o))[6:-1] 
					return
				else:
					output = p([v for v in o], indent, listLimit, ellipsisLimit, nestedListLimit, directPrint)
					output += '\n(Unrecognized type - iteration attempted for type <%r>)' % str(type(o))[6:-1] 
					return output			
			except Exception, error:
				out += [repr(o)]
		else:
			out += [repr(o)]
	out += ['']
	
	output = '\n'.join(out)
	if directPrint:
		print output
	else:
		return output


def displayhook(obj):
	"""Make pretty things the default!"""
	# don't print None by itself, like normal
	if obj is None:
		return
	try:
		# Special override cases:
		# get a bit more info for frames (super handy for debug)
		if isinstance(obj, (FrameType, CodeType)):
			pdir(obj, recursePrettily=True, recurseSkips=set(['f_builtins', 'f_globals']))
		# Default cases:
		# pretty print the default nice things
		elif isinstance(obj, PRETTY_PRINT_TYPES):
			p(obj)
		# normal prints for normal stuff
		elif isinstance(obj, (int,float,long,str,unicode)):
			print obj
		# replicate help/info for modules and stuff
		elif isinstance(obj, (ModuleType, BuiltinFunctionType, BuiltinMethodType, MethodType, UnboundMethodType)):
			pdir(obj)
		# don't poke into generators, lest some of the introspection consume it...
		elif isinstance(obj, (GeneratorType, XRangeType)):
			print repr(obj)
		# classes / types should be dir'd (throws errors on instances)
		elif issubclass(obj, (type, object, JavaClass)):
			pdir(obj)
	# everything else gets a normal repr treatment. 
	except:
		print repr(obj)			
	
	# Save to _ in builtin, per docs
	__builtin__._ = obj
	

def prettify(obj):
	"""Figure out how to show a thing"""
	# don't print None by itself, like normal
	if obj is None:
		return
	try:
		# Special override cases:
		# get a bit more info for frames (super handy for debug)
		if isinstance(obj, (FrameType, CodeType)):
			return pdir(obj, recursePrettily=True, recurseSkips=set(['f_builtins', 'f_globals']), directPrint=False)
		# Default cases:
		# pretty print the default nice things
		elif isinstance(obj, PRETTY_PRINT_TYPES):
			return p(obj, directPrint=False)
		# normal prints for normal stuff
		elif isinstance(obj, (int,float,long,str,unicode)):
			return obj
		# replicate help/info for modules and stuff
		elif isinstance(obj, (ModuleType, BuiltinFunctionType, BuiltinMethodType, MethodType, UnboundMethodType)):
			return pdir(obj, directPrint=False)
		# don't poke into generators, lest some of the introspection consume it...
		elif isinstance(obj, (GeneratorType, XRangeType)):
			return repr(obj)
		# classes / types should be dir'd (throws errors on instances)
		elif issubclass(obj, (type, object, JavaClass)):
			return pdir(obj, directPrint=False)
	# everything else gets a normal repr treatment. 
	except:
		return repr(obj)			
		

def install(sys_scope=None):
	"""Inject pretty printing into the interactive system scope."""
	if sys_scope is None:
		import sys as sys_scope
	sys_scope.displayhook = displayhook
	
def uninstall(sys_scope=None):
	"""Revert the interactive printing to the default builtin displayhook."""
	if sys_scope is None:
		import sys as sys_scope
	sys_scope.displayhook = sys_scope.__displayhook__


# l = [1,2,3,'wer',6]
# p(l)

# ll = [[1,2,3],(4,5.33,6),[9.9,8]]
# p(ll)

# pd = system.util.getSessionInfo()
# p(pd.getUnderlyingDataset())