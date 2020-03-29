"""
		Helper functions for interacting with data a bit easier.
"""


from com.inductiveautomation.ignition.common import BasicDataset
from itertools import izip as zip
import re


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'


def datasetToListDict(dataset):
	"""Converts a dataset into a list of dictionaries. 
	Convenient to treat data on a row-by-row basis naturally in Python.
	
	>>> from shared.tools.examples import simpleDataset
	>>> datasetToListDict(simpleDataset)
	[{'a': 1, 'b': 2, 'c': 3}, {'a': 4, 'b': 5, 'c': 6}, {'a': 7, 'b': 8, 'c': 9}]
	"""
	header = [str(name) for name in dataset.getColumnNames()]
	try:
		return [dict(zip(header, row)) for row in zip(*dataset.data)]
	except:
		return [dict(zip(header, row)) for row in zip(*dataset.delegateDataset.data)]

		
def datasetToDictList(dataset):
	"""Converts a dataset into a dictionary of column lists.
	Convenient for treating data on a specific-column basis.
	
	>>> from shared.tools.examples import simpleDataset
	>>> datasetToDictList(simpleDataset)
	{'a': [1, 4, 7], 'b': [2, 5, 8], 'c': [3, 6, 9]}
	"""
	header = [str(name) for name in dataset.getColumnNames()]
	return dict(zip( header, [dataset.getColumnAsList(i) for i in range(len(header))] ))


def gatherKeys(data):
	"""Gather all the possible keys in a list of dicts.
	(Note that voids in a particular row aren't too bad.)
	
	>>> from shared.tools.examples import complexListDict
	>>> gatherKeys(complexListDict)
	['date', 'double', 'int', 'string']
	"""
	keys = set()
	for row in data:
		keys.update(row)
	return sorted(list(keys))


def listDictToDataset(data, keys=None):
	"""Converts a list of dictionaries into a dataset.
	A selection of keys can be requested (and reordered), where missing entries
	are filled with None values.

	>>> from shared.tools.pretty import p
	>>> from shared.tools.examples import simpleListDict
	>>> ld2ds = listDictToDataset(simpleListDict, keys=['c','b'])
	>>> p(ld2ds)
	"ld2ds" <DataSet> of 3 elements and 2 columns
	=============================================
			  c                     |  b                    
			   <java.lang.Integer>  |   <java.lang.Integer> 
	--------------------------------------------------------
	   0 |                        3 |                      2
	   1 |                        6 |                      5
	   2 |                        9 |                      8
	"""
	# gather the keys, in case there are voids in the data
	if not keys:
		keys = gatherKeys(data)
	
	columns = dict((key,[]) for key in keys)
	for row in data:
		for key in keys:
			columns[key].append( row.get(key, None) )

	aligned = zip(*[columns[key] for key in keys])
		
	return system.dataset.toDataSet(keys, aligned)
		