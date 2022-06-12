"""
	Hoist a module at run time

	Not all code can run reasonably in a Venv block. For example,
	  you can't use `from __future__ import with_statement` inside
	  a function definition. But you _can_ execute it as a block.

	The following implements the `hotload` function which gets around that.
"""

from zipfile import ZipFile
from StringIO import StringIO as BytesIO

import sys, imp, os

#namespace = 'hotload'


def new_module(module_path):
	"""Create and prime a new module for horking into the `sys.modules`"""
	mod = imp.new_module(module_path)
	mod.__file__ = module_path
	mod.__name__ = module_path
	mod.__package__ = module_path.rpartition('.')[0]
	return mod
	
	
def setdefault_module(sys_context, module_path):
	"""Helper to simplify gettering a module."""
	if not module_path in sys_context.modules:
		module = new_module(module_path)
		sys_context.modules[module_path] = module
	else:
		module = sys_context.modules[module_path]
	return module
	
	
def ensure_import_chain(target_module_path, sys_context=None):
	"""
	In order to chain module imports, child modules need to be
	  an attribute of the parent. This ensures that every child
	  has a parent, and that the parent knows who they are. Aww.
	"""
	# check for trivial chain of one
	# print 'Chaining %s' % target_module_path
	if not '.' in target_module_path:
		return

	module_path_parts = target_module_path.split('.')
	supporting_packages = ['.'.join(module_path_parts[0:i]) 
								    for i 
								    in range(1,len(module_path_parts))]
	# prime the loop
	package_chain = supporting_packages[:]
	package_chain.append(target_module_path)
	
	# chain the child connections
	parent_module = setdefault_module(sys_context, package_chain[0])
	for module_path in package_chain[1:]:
		child_module = setdefault_module(sys_context, module_path)
		child_module_name = module_path.rpartition('.')[2]
		setattr(parent_module, child_module_name, child_module)
		parent_module = child_module

	

def hotload(module_zip_binary, global_context=None, namespace='', sys_context=None, force_replace=False):
	"""
	Load a zip file's python code as a module at runtime.

	Note that the folder path is assumed to be the module paths.
	  This also does NOT use any optimizations. Use this strictly
	  for runtime monkey patching/loading.

	This simply executes the Python files and stores the namespace
	  as a new module in `sys.modules`.
	"""
	if global_context is None:
		global_context = {}
	else:
		# don't mutate the original
		global_context = global_context.copy()
		
	if sys_context is None:
		import sys as sys_context
		
	module_binary_io = BytesIO(module_zip_binary)
	module_files = ZipFile(module_binary_io, 'r')
	
	module_code = {}
	
	for z in module_files.infolist():
		module_path_parts = z.filename.split('/')
		if namespace:
			module_path_parts = namespace.split('.') + module_path_parts
		module_path = '.'.join(module_path_parts)
		
		# only compile python code, then trim the extension to get the path
		if not module_path.endswith('.py'):
			continue
		module_path = module_path[:-3]
		
		# have Python build the module
		raw_code = module_files.read(z.filename)
		local_context = global_context.copy()
		code = compile(raw_code, '<hotloader: %s>' % module_path, 'exec')
		module_code[module_path] = code
	
	remaining = set(module_code)
	
	if force_replace:
		for module_path in remaining:
			if module_path in sys_context.modules:
				del sys_context.modules[module_path]
	
	while remaining:
	
		for module_path in remaining:
			try:
				local_context = {
					'__name__': module_path,
					'__file__': module_path,
					}
				code = module_code[module_path]
				# pass local_context as both global and local dict
				#  that way as it executes, nested functions can access the global scope
				result = eval(code, local_context)
			
			# Should we try to load them out of order, just move on
			except ImportError, err:
				#print '== Compile error: %s --> %r' % (module_path, err)
				continue

			#print 'Module compiled: %s' % module_path
			
			# create and construct module
			module = new_module(module_path)
			for name, obj in local_context.items():
				setattr(module, name, obj)
					
			# apply to sys and cache for cross-linking
			sys_context.modules[module_path] = module
			
			ensure_import_chain(module_path, sys_context)
			
			remaining.remove(module_path)
			break
		else:
			raise ImportError("All modules could not be loaded!\nLast error in %s: %r" % (module_path, err))
		
	# clean up to ensure packages are handled
	packages = [mp for mp in module_code if '%s.__init__' % mp in module_code]
	for module_path in module_code:
		if '%s.__init__' % mp in module_code:	
			sys.modules[module_path].__path__ = module_path
		else:
			sys.modules[module_path].__package__ = module_path.rpartition('.')[0]





from java.net import URLClassLoader, URL
from java.io import File
from jarray import array
from java.lang import Class as JavaClass
from java.lang import Exception as JavaException, NoClassDefFoundError
from java.util.jar import JarFile



class JarClassLoader(object):
	"""Load in jars via an alternate method from just injecting into sys.path

	Jython can natively load jar libraries very easily, but occasionally has weird
	trouble loading inner classes (or something). At the least, grinding through and
	manually injecting the class objects seems to help.

	An attempt was made to make the class loading lazy, but the import mechanics
	do not seem to resolve properties on load, returning the property instead
	of the class itself. Oh well.
	"""
	def __init__(self, jar_file_path):
		self.jar_file_path = jar_file_path
		self.urlLoader = URLClassLoader(array([File(jar_file_path).toURI().toURL()], URL))
		self.jarFile = JarFile(jar_file_path)
		
		self.class_list = set(
				str(class_name)[:-6].replace('/', '.') 
				for class_name
				in self.jarFile.entries()
				if str(class_name).endswith('.class')
			)
			
		self.packages = {}
		for class_path in self.class_list:
			package_path, _, class_name = class_path.rpartition('.')
			if not package_path in self.packages:
				self.packages[package_path] = set()
			self.packages[package_path].add(class_name)

		self.class_cache = {}
		
		self.inject_sys()
		
	def inject_sys(self):
		for package_path in sorted(self.packages):
			module = imp.new_module(package_path)
			module.__file__ = os.path.join(self.jar_file_path, package_path)
			module.__name__ = package_path
			module.__package__ = '.'.join(package_path.split('.')[:1]) # I forget why this is needed...
			
			for class_name in self.packages[package_path]:
				class_name = class_name.partition('$')[0]
				setattr(module, class_name, self.get_class(package_path, class_name))
			
			sys.modules[package_path] = module
			
		
	def get_class(self, package_path, class_name):
		if not (package_path, class_name) in self.class_cache:
			loaded_class = self.urlLoader.loadClass(package_path + '.' + class_name)
			self.class_cache[(package_path, class_name)] = loaded_class			
		return self.class_cache[(package_path, class_name)]



def jar_class_grind(jar_paths):
	for jar_path in jar_paths:
		_ = JarClassLoader(jar_path)