import unittest, doctest

import sys

from shared.corso.venv import Venv


# doctest.run_docstring_examples(Venv, globals(), optionflags=doctest.ELLIPSIS)


class VenvTestCases(unittest.TestCase):

	@staticmethod
	def _createScopeInFunction():
		modGen = Venv('examples.venv.functionScope').anchorModuleStart()
		def foo():
			return 'foo!'
		modGen.anchorModuleEnd().bootstrapModule()

	def test_bootstrapInFunction(self):
		def importForScopeInFunction():
			from examples.venv.functionScope import foo 

		self.assertRaises(ImportError, importForScopeInFunction)
		self._createScopeInFunction()
		self.assertNotIn('foo', locals())
		from examples.venv.functionScope import foo
		self.assertEqual(foo(), 'foo!')

	def test_withStatementEnvironment(self):
		def createEnvironment():
			venv = Venv('examples.venv.presetScope').anchorModuleStart()
			def bar():
				return 'bar!'
			venv.anchorModuleEnd()
			return venv

		def importForWithStatementIsolation():
			from examples.venv.presetScope import bar
		def callBar():
			bar()
		self.assertRaises(ImportError, importForWithStatementIsolation)
		self.assertNotIn('bar', locals())

		with createEnvironment():
			from examples.venv.presetScope import bar
			self.assertEqual(bar(), 'bar!')
			abc = 123
			
		self.assertNotIn('bar', locals())
		self.assertNotIn('abc', locals())
		self.assertRaises(ImportError, importForWithStatementIsolation)


suite = unittest.TestLoader().loadTestsFromTestCase(VenvTestCases)
unittest.TextTestRunner(verbosity=1).run(suite)
