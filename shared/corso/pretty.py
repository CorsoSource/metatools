"""
	A handy set of pretty printers for dumping info in Ignition.

	These are meant to be used with a console.
"""


import re, math, textwrap
from java.lang import Exception as JavaException
from com.inductiveautomation.ignition.common import BasicDataset
from com.inductiveautomation.ignition.common.script.builtin.DatasetUtilities import PyDataSet
from shared.corso.meta import getObjectName, getFunctionCallSigs, sentinel


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['p','pdir']


quotePattern = re.compile("""^('.*'|".*")$""")


def pdir(o, indent='  ', ellipsisLimit=120, includeDocs=False, skipPrivate=True, directPrint=True):
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
		
	dotdotdot = lambda s: s if not ellipsisLimit or len(s)<=ellipsisLimit else '%s...' % s[:ellipsisLimit-3]
	
	out = []	
	
	name = getObjectName(o,estimatedDepth=2)
	if name:
		out += ['%sProperties of "%s" <%s>' % (indent, name, str(type(o))[6:-1])]
	else:
		out += ['%sProperties of <%s>' % (indent, str(type(o))[6:-1])]
	out += ['%s%s' % (indent, '='*len(out[0]))]
	
	try:
		joinClause = '\n---\n'
		callExample = '%s%s' % (indent, getFunctionCallSigs(o, joinClause),)
		out += callExample.split(joinClause)
		out += ['%s%s' % (indent, '-'*max([len(line) for line in callExample.split(joinClause)] + [1]))]
	except:
		pass
	
	if '__doc__' in dir(o) and o.__doc__:
		docstringLines = o.__doc__.splitlines()
		if len(docstringLines) > 1:
			docstringLines = [docstringLines[0]] + textwrap.dedent('\n'.join(docstringLines[1:])).splitlines()
		maxDocLen = max([len(line) for line in docstringLines] + [1])
		docPattern = '%%s%%-%ds' % maxDocLen
		for line in docstringLines:
			out += [docPattern % (indent, line)]
		else:
			out += ['']
	
	attributes = [attribute for attribute in dir(o)
				  if not (attribute.startswith('_') and skipPrivate)]
					
	# preprocessing
	attrTypes = []
	attrTypeStrings = []
	attrReprs = []
	attrDocs = []
	for attribute in sorted(attributes):
	
		try:
			attr = getattr(o,attribute)
			attrType = type(attr)
			attrTypes.append(attrType)
			
			typeStr = str(attrType)[7:-2]
			typeStr = typeStr.partition('$')[0]
			attrTypeStrings.append(typeStr)
			try:
				attrReprs.append(getFunctionCallSigs(attr))
			except:
				try:
					attrReprs.append(repr(attr))
				except:
					try:
						attrReprs.append(str(attr))
					except:
						attrReprs.append('< ? >')
				
			try:
				attrDocs.append(' '.join(attr.__doc__.splitlines()))	
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
		
	maxAttrLen = max([len(attribute) 
					  for attribute in attributes] + [0])
	
	maxTypeLen = 2 + max([len(attrTypeStr) 
						  for attrTypeStr in attrTypeStrings
						  if not attrTypeStr in skipTypes] + [0])
						  
	maxReprLen = max([len(attrRepr) 
						  for attrTypeStr,attrRepr in zip(attrTypeStrings,attrReprs)
						  if not attrTypeStr in skipTypes] + [0])
	if ellipsisLimit and maxReprLen > ellipsisLimit:
		maxReprLen = ellipsisLimit
						  
	attrPattern = '%s%%-%ds   %%-%ds   %%-%ds'          % (indent, maxAttrLen+2, maxReprLen+2, maxTypeLen+2)
	attrDocPattern = '%s%%-%ds   %%-%ds   %%-%ds   %%s' % (indent, maxAttrLen+2, maxReprLen+2, maxTypeLen+2)
	
	out += [attrPattern % ('Attribute', 'Repr', '<Type>')]
	out += [attrPattern % ('-'*maxAttrLen, '-'*maxReprLen, '-'*maxTypeLen)]
	
	# calculating
	for attrType,attrTypeStr,attribute,attrRepr,attrDoc in zip(attrTypes,attrTypeStrings,attributes,attrReprs,attrDocs):
		
		if attrTypeStr in skipTypes:
			attrTypeStr = ''
			attrRepr = ''
		else:
			attrTypeStr = '%s' % attrTypeStr

		attribute = attribute.strip()
		attrTypeStr =  attrTypeStr.strip()
		attrRepr = attrRepr.strip()
		
		if len(attrRepr) >= maxReprLen:
			attrRepr = '%s...' % attrRepr[:maxReprLen-4]
		if len(attrTypeStr) >= maxReprLen:
			attrTypeStr = '%s...' % attrTypeStr[:maxReprLen-4]

		if attrDoc and includeDocs:
			outStr = attrDocPattern % (attribute, attrRepr, attrTypeStr, attrDoc)
		else:
			outStr = attrPattern % (attribute, attrRepr, attrTypeStr)
		
		outStr = ' -- '.join(outStr.splitlines())
		out += [outStr]
	
	out += ['']

	output = '\n'.join(out)
	if directPrint:
		print output
	else:
		return output



def p(o, indent='  ', listLimit=42, ellipsisLimit=80, directPrint=True):
	"""Pretty print objects. This helps make lists, dicts, and other things easier to understand.
	Handy for quickly looking at datasets and lists of lists, too, since it aligns columns.
	"""
	out = []
	
	strElePattern = '%%-%ds'
	numElePattern = '%%%ds'	
	colSep = ' |  '
	
	if isinstance(o, (BasicDataset,PyDataSet)):
		ds = o
		if isinstance(ds, PyDataSet):
			ds = ds.getUnderlyingDataset()
			out += ['"%s" <PyDataSet> of %d elements and %d columns' % (getObjectName(o,estimatedDepth=2), ds.getRowCount(), ds.getColumnCount())]
		else:
			out += ['"%s" <DataSet> of %d elements and %d columns' % (getObjectName(o,estimatedDepth=2), ds.getRowCount(), ds.getColumnCount())]
		out += ['='*len(out[0])]
		
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
		out += ['-'*len(out[-1])]
		
		for i, row in enumerate(data):
			out += [rowPattern % tuple([i] + list(row))]		
		
		
	elif isinstance(o, (list, tuple)):
		out += ['"%s" <%s> of %d elements' % (getObjectName(o,estimatedDepth=2), str(type(o))[6:-1],len(o))]
		
		# preprocessing
		maxRowWidth = int(math.floor(math.log10(len(o))))
		
		# column alignment, if any
		try:
			colEleWidths = [max([len(repr(r)) for r in row] + [1]) for row in zip(*o)]
		except:
			colEleWidths = [max([len(repr(element)) for element in o] + [1])]
				
		prefixPattern =  '%s %%%dd ' %  (indent, maxRowWidth + 1)
		preLisPattern =  '%s[%%%dd]' %  (indent, maxRowWidth + 1)
		preTupPattern =  '%s(%%%dd)' %  (indent, maxRowWidth + 1)
			
		# element printing
		for i,element in enumerate(o):
			
			#if isinstance(element, (list,tuple,dict)):
			if isinstance(element, dict):
				nestedPattern = '%s{%%%dd}  %%s' % (indent, maxRowWidth + 1)
				out += [nestedPattern % (i, p(element, indent+' '*(maxRowWidth+1+2+2), directPrint=False))]
				continue
			
			if not isinstance(element, (list,tuple)):
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
			else:
				rowColPatterns = [strElePattern % w if isinstance(r, (str,unicode)) else numElePattern % w
													for r,w in zip(element,colEleWidths)]						
				if isinstance(element, list):
					rowPattern = preLisPattern + '  ' + colSep.join(rowColPatterns)
				else:
					rowPattern = preTupPattern + '  ' + colSep.join(rowColPatterns)
					
				rowRepr = [i] + [rowColPattern % repr(rr) for rowColPattern, rr in zip(rowColPatterns,element)]
				unaligned = [repr(rr) for i,rr in enumerate(element) if i >= len(rowColPatterns)]
				rowPatternPattern = colSep + '%s'
				rowPattern += rowPatternPattern * len(unaligned)
				rowRepr = tuple(rowRepr + unaligned)
				out+= [rowPattern % rowRepr]
			
			
			if listLimit and i >= listLimit-1:
				out += ['%s... %d ellided (of %s total)' % (indent, len(o)-i-1, len(o))]
				break
				
				
	elif isinstance(o, dict):
		out.append('"%s" <%s> of %d elements' % (getObjectName(o,estimatedDepth=2), str(type(o))[6:-1],len(o)))
		
		# preprocessing
		maxKeyWidth = max([len(repr(key)) for key in o.keys()] + [1])
		maxValWidth = max([len(repr(val)) for val in o.values()] + [1])
		
		elementPattern = '%s%%%ds : %%-%ds' % (indent, maxKeyWidth, maxValWidth)
		
		# element printing
		for i,key in enumerate(sorted(o.keys())):
			element = o[key]
			
			if isinstance(element, (list,tuple,dict)) and element is not o: #don't recurse here!
				nestedPattern = '%s%%%ds : %%s' % (indent, maxKeyWidth)
				out += [nestedPattern % (key, p(element, indent+' '*(maxKeyWidth+3), directPrint=False))]
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
		
	
	else:
		out += [repr(o)]
	
	out += ['']
	
	output = '\n'.join(out)
	if directPrint:
		print output
	else:
		return output



# l = [1,2,3,'wer',6]
# p(l)

# ll = [[1,2,3],(4,5.33,6),[9.9,8]]
# p(ll)

# pd = system.util.getSessionInfo()
# p(pd.getUnderlyingDataset())