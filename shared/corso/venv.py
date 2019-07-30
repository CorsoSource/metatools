"""
	Virtual environment bootstrapping
"""



import sys,imp

from shared.corso.meta import currentStackDepth
from shared.corso.pretty import p,pdir

try:
	_ = sys.modules.pop('asdf')
	_ = sys.modules.pop('asdf.qwer')
	_ = sys.modules.pop('asdf.qwer.zxcv')
	
except:
	pass


class Venv(object):
	"""Hoists a block of code as a module. 
	Use to test and virtually bootstrap code in environments where globals can not be easily modified.
	
	Example for generating scope: the commented lines bring a NameError
		def someFunctionScope():
			modGen = Venv('asdf.qwer.zxcv').anchorModuleStart()
			def foo():
				print 'foo!'
			modGen.anchorModuleEnd().bootstrapModule()
		#someFunctionScope()              # uncomment to fix ImportError on asdf
		#from asdf.qwer.zxcv import foo   # uncomment to fix NameError on foo
		foo()

	Example in using it as an in-line virtual environment:
		def createEnvironment():
			venv = Venv('asdf.qwer.zxcv').anchorModuleStart()
			def foo():
				print 'foo!'
			venv.anchorModuleEnd()
			return venv

		with createEnvironment():
			from asdf.qwer.zxcv import foo
			abc = 123
			foo()
		# attempt to reference abc, or foo, or to import asdf.qwer.zxcv
	"""
	
	def __init__(self, modulePath=None, overwriteInterlock=False):
		self._setCallingContext()
		
		if modulePath in self._getCallingFrameSys().modules.keys():
			if not overwriteInterlock:
				raise ImportError('Venv interlocked because module already exists in scope: %s' % modulePath) 
		
		self.modulePath = modulePath
		self.package = {}
		self._createdScope = []
	
	def _setCallingContext(self, relativeOverride=0):
		self._callingStackDepth = currentStackDepth() - 1 - 1 + relativeOverride

	def _getCallingFrame(self):
		return sys._getframe(currentStackDepth() - self._callingStackDepth)
	
	def _getCallingFrameSys(self):
		frame = self._getCallingFrame()
		scopedSys = frame.f_locals.get('sys', frame.f_globals.get('sys',None))
		if scopedSys is None:
			raise NameError('Venv needs sys to be imported into scope _before_ running!')
		return scopedSys
		
	def anchorModuleStart(self):
		f_locals = self._getCallingFrame().f_locals
		self.startingSnapshot = frozenset(f_locals.keys())
		return self
		
	def anchorModuleEnd(self):
		f_locals = self._getCallingFrame().f_locals
		self.endingSnapshot = frozenset(f_locals.keys())
		addedItems = self.endingSnapshot.difference(self.startingSnapshot)
		self.package.update(dict([(item,f_locals[item]) for item in addedItems]))
		return self
	
	@staticmethod
	def _initializeNewModule(modulePath):
		"""see https://github.com/reingart/pymotw3/blob/master/source/sys/sys_meta_path.py"""
		mod = imp.new_module(modulePath)
		mod.__file__ = modulePath
		mod.__name__ = modulePath
		mod.__package__ = '.'.join(modulePath.split('.')[:1])
		return mod
	
	def bootstrapModule(self):
		modulePathParts = self.modulePath.split('.')
		supportingPackages = ['.'.join(modulePathParts[0:i]) for i in range(1,len(modulePathParts))]
		for parentPath in supportingPackages:
			if not parentPath in sys.modules:
				self._initializeNewModule(parentPath)
				sys.modules[parentPath] = imp.new_module(parentPath)
				self._createdScope.append(parentPath)
		
		newModule = self._initializeNewModule(self.modulePath)
		
		for key,value in self.package.items():
			setattr(newModule, key, value)
		sys.modules[self.modulePath] = newModule
		self._createdScope.append(self.modulePath)

	def _purgeScope(self):
		scopedSys = self._getCallingFrameSys()
		for modulePath in reversed(sorted(self._createdScope)):
			_ = scopedSys.modules.pop(modulePath)
			
	def __enter__(self):
		self.bootstrapModule()
		self._setCallingContext()
		_ = self.anchorModuleStart()
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		self._purgeScope()
		self.package = {}
		_ = self.anchorModuleEnd()
		f_locals = self._getCallingFrame().f_locals
		for key,value in self.package.items():
			f_locals.pop(key)
