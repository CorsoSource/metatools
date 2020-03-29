import unittest, doctest

from shared.tools.meta import sentinel, getFunctionCallSigs

doctest.run_docstring_examples(sentinel,globals())
doctest.run_docstring_examples(getFunctionCallSigs,globals())


from shared.tools.meta import currentStackDepth, getObjectByName, getObjectName


class ObjectSearchTestCase(unittest.TestCase):

	def test_stackSearch(self):
		# Generate a stack search 
		def foo():
			x = 33
			def bar():
				y = 2
				def baz():
					z = 3
					x = 725
					
					currentDepth = currentStackDepth()
					
					# Start in this stack frame, go into the past
					self.assertEqual(725, getObjectByName('x'))
					# Start at the deepest past, and go towards the current stack frame
					self.assertEqual(33, getObjectByName('x', startRecent=False))
					# Start at the deepest past and go deeper (before foo was defined!)
					self.assertEqual(None, getObjectByName('x', currentDepth))
					# start at the deepest past and come towards the current stack frame
					self.assertEqual(33, getObjectByName('x', currentDepth, startRecent=False))
					
					self.assertEqual('foo', getObjectName(foo))
				baz()	
			bar()
		foo()
		
	def test_PythonFunctionSigs(self):
		# Generate a few different functions to verify signatures.
		def fun1():
			pass
		def fun2(x,y,z=5):
			pass
		self.assertEqual('()', getFunctionCallSigs(fun1))
		self.assertEqual('(x, y, z=5)', getFunctionCallSigs(fun2))
		
	def test_JavaFunctionSigs(self):
		from java.util import Random
		
		# Check the no args case
		self.assertEqual('()', getFunctionCallSigs(Random().nextBoolean))
		# Check the single call method case
		self.assertEqual('(<long>)', getFunctionCallSigs(Random().setSeed))
		# Check the many ways to call case
		self.assertEqual('() -OR- (<long>) -OR- (<int>, <int>) -OR- (<long>, <int>, <int>)', getFunctionCallSigs(Random().ints))
		# Try a different join method
		self.assertEqual('()|(<long>)|(<int>, <int>)|(<long>, <int>, <int>)', getFunctionCallSigs(Random().ints, joinClause='|'))
	
	
suite = unittest.TestLoader().loadTestsFromTestCase(ObjectSearchTestCase)
unittest.TextTestRunner(verbosity=2).run(suite)
	