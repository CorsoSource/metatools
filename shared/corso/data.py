"""
		Helper functions for interacting with data a bit easier.
"""

from com.inductiveautomation.ignition.common import BasicDataset
from itertools import izip as zip
import re


def datasetToListDict(dataset):
	header = [str(name) for name in dataset.getColumnNames()]
	try:
		return [dict(zip(header, row)) for row in zip(*dataset.data)]
	except:
		return [dict(zip(header, row)) for row in zip(*dataset.delegateDataset.data)]

		
def datasetToDictList(dataset):
	header = [str(name) for name in dataset.getColumnNames()]
	return dict(zip( header, [dataset.getColumnAsList(i) for i in range(len(header))] ))


def gatherKeys(data):
	keys = set()
	for row in data:
		keys.update(row)
	return sorted(list(keys))


def listDictToDataset(data, keys=None):
	# gather the keys, in case there are voids in the data
	if not keys:
		keys = gatherKeys(data)
	
	columns = dict((key,[]) for key in keys)
	for row in data:
		for key in keys:
			columns[key].append( row.get(key, None) )

	aligned = zip(*[columns[key] for key in keys])
		
	return system.dataset.toDataSet(keys, aligned)
		

def genRecordSet(header):
	"""Returns something like a namedtuple. 
	Designed to have lightweight instances while having many convenient ways
	to access the data.
	"""
	
	if isinstance(header, BasicDataset):
		rawFields = tuple(h for h in header.getColumnNames())
	else:
		rawFields = tuple(h for h in header)	
		
	unsafePattern = re.compile('[^a-zA-Z0-9_]')
	sanitizedFields = [unsafePattern.sub('_', rf) for rf in rawFields]
	
	dupeCheck = set()
	for i,(sf,f) in enumerate(zip(sanitizedFields, rawFields)):
		if sf in dupeCheck:
			n = 1
			while '%s_%d' % (sf,n) in dupeCheck:
				n += 1
			sanitizedFields[i] = '%s_%d' % (sf,n)
		
		dupeCheck.add(sanitizedFields[i])
	
	sanitizedFields = tuple(sanitizedFields)
		
	class RecordSet(object):
		"""Inspired by recipe in Python2 standard library.
		https://docs.python.org/2/library/collections.html#collections.namedtuple
		
		But doesn't follow the same design for easier overloading.
		"""
		__slots__ = ('_tuple')
		_fields = tuple(rf for rf in rawFields)
		_lookup = dict(kv for kv 
					   in zip(rawFields + sanitizedFields, range(len(_fields))*2) )
		
		_reprString = 'RS(%s)' % (', '.join("'%s'=%%r" % f for f in _fields),)
		
		
		def __init__(self, iterable):
			if len(iterable) <> len(self._fields):
				raise TypeError('Expected %d arguments, but got %d' % (len(self._fields), len(iterable)))
			self._tuple = tuple(iterable)
		
			
		def _asdict(self):
			return dict(zip(self._fields, self))
			
		@classmethod
		def keys(cls):
			return cls._fields
			
		def values(self):
			return self._tuple
			
			
		def _replace(_self, **keyValues):
			result = _self._make(map(keyValues.pop, _self.rawFields, _self))
			if keyValues: # make sure all got consumed by the map
				raise ValueError('Got unexpected field names: %r' % keyValues.keys())
			self._tuple = result
	
		def __getitem__(self, key):
			try: # EAFP
				return self._tuple[key]
			except (TypeError,IndexError):
				try:
					return self._tuple[key]
				except TypeError:
					raise ValueError('Key out of range or invalid: "%r"' % key)
					
	
		def __getattr__(self, attribute):
			"""Allow the keys to be used as direct attributes."""
			return self[attribute]
			
		def __iter__(self):
			"""Redirect to the tuple stored when iterating."""
			return (v for v in self._tuple)
			
	
		def __repr__(self):
			'Format the representation string for better printing'
			return self._reprString % self._tuple
		def __getnewargs__(self):
		
		    'Return self as a plain tuple.  Used by copy and pickle.'
		    return tuple(self)
		
		def __getstate__(self):
		    'Exclude the OrderedDict from pickling'
		    pass
	    
	return RecordSet