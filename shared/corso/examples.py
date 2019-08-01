"""
	Examples for use with documentation or testing.
"""


from org.apache.commons.lang3.time import DateUtils
from java.util import Date


simpleListList = [range(i,i+3) for i in range(1,9,3)]

simpleDataset = system.dataset.toDataSet(list('abc'),simpleListList)

complexDataset = system.dataset.toDataSet(
	['string', 'int', 'double', 'date'], 
	[	[ 'asdf'     , 1    , 10.1                    , DateUtils.addMinutes(Date() , 33)   ] ,
		[ 'qwer'     , 3    , 12.3                    , DateUtils.addHours(Date()   , -102) ] ,
		[ '1q2w3e4r' , -34  , 1000.000000000000000001 , DateUtils.setYears(Date()   , 1999) ] ,
		[ ''         , None , -0.000                  , Date()                              ] ,
	]	)

simpleDictList = {'a': [1, 4, 7], 
				  'b': [2, 5, 8], 
				  'c': [3, 6, 9],
				  }

complexDictList = {  'date': [	DateUtils.addMinutes(Date(), 33), 
 								DateUtils.addHours(Date(), -102), 
 								DateUtils.setYears(Date(), 1999), 
 								Date(),
 							], 
 					 'string': [ 'asdf', 'qwer', '1q2w3e4r', '',], 
 					 'double': [10.1, 12.3, 1000.0, -0.0,], 
 					 'int': [1, 3, -34, None,]
 				  }

simpleListDict = [{'a': 1, 'b': 2, 'c': 3}, 
				  {'a': 4, 'b': 5, 'c': 6}, 
				  {'a': 7, 'b': 8, 'c': 9},
				  ]

complexListDict = [ { 'date': DateUtils.addMinutes(Date(), 33) , 
				  	  'string': 'asdf', 
				  	  'double': 10.1, 
				  	  'int': 1
				  	 }, 
				  	{ 'date': DateUtils.addHours(Date(), -102), 
				  	  'string': 'qwer', 
				  	  'double': 12.3, 
				  	  'int': 3
				  	}, 
				  	{ 'date': DateUtils.setYears(Date(), 1999), 
				  	  'string': '1q2w3e4r', 
				  	  'double': 1000.0, 
				  	  'int': -34
				  	}, 
				  	{ 'date': Date(), 
				  	  'string': '', 
				  	  'double': -0.0, 
				  	  'int': None
				  	} ]