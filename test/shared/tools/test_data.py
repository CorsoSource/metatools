import unittest, doctest

from org.apache.commons.lang3.time import DateUtils
from java.util import Date

from shared.tools.data import *


doctest.run_docstring_examples(datasetToListDict,globals())
doctest.run_docstring_examples(datasetToDictList,globals())
doctest.run_docstring_examples(gatherKeys,globals())
doctest.run_docstring_examples(listDictToDataset,globals())


class RecordSetTestCase(unittest.TestCase):

	def setUp(self):
		self.columnNames = 'c1 c2 c3'.split()
		self.numColumns = len(self.columnNames)
		self.numRows = 4
		self.RecordSet = genRecordSet(self.columnNames)

	def tearDown(self):
		pass
	
	# Test different inputs
	def test_readListOfLists(self):
		# generate source data
		listOfLists= [list(range(i,i+self.numColumns)) 
					  for i in range(1,self.numRows*self.numColumns,self.numColumns)]
		
		# generate test data
		listOfRecordSets = [self.RecordSet(row) for row in listOfLists]
		
		# check dimensions
		self.assertTrue(all(len(listOfRecordSets[i].keys()) for i in range(self.numColumns)))
		self.assertEqual(len(listOfRecordSets), self.numRows)
		
		# verify data imported correctly
		for lotRow,lorsRow in zip(listOfLists, listOfRecordSets):
			self.assertEqual(lotRow,list(lorsRow))
	
	# Test different inputs
	def test_readListOfTuples(self):
		# generate source data
		listOfTuples = [tuple(range(i,i+self.numColumns)) 
						for i in range(1,self.numRows*self.numColumns,self.numColumns)]
		
		# generate test data
		listOfRecordSets = [self.RecordSet(row) for row in listOfTuples]
		
		# check dimensions
		self.assertTrue(all(len(listOfRecordSets[i].keys()) for i in range(self.numColumns)))
		self.assertEqual(len(listOfRecordSets), self.numRows)
		
		# verify data imported correctly
		for lotRow,lorsRow in zip(listOfTuples, listOfRecordSets):
			self.assertEqual(lotRow,tuple(lorsRow))


suite = unittest.TestLoader().loadTestsFromTestCase(RecordSetTestCase)

unittest.TextTestRunner(verbosity=2).run(suite)