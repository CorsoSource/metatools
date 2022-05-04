from types import ModuleType

import sys
import re


class Antikythera(ModuleType):
	"""
	This is a metaclass that sets up the mechanisms that allow
	the class to behave like a module. It is a module, but it
	will act like one here as well.

	Importantly, it will also inject itself into sys.modules
	correctly as well. This is important because the imp
	and __import__ mechanics will not do this correctly.
	"""

	def __new__(cls, clsname, bases, attrs):



		return cls


	def __getattr__(cls, attribute):
		if attribute in cls.overrides:
			return getattr(cls, attribute)
		elif attribute in cls.submodules:
			return cls.submodules[attribute]
		else:
			return super(MetaModule, cls).__getattr__(attribute)



class AutoModule(object):
	"""
	Base class to subclass for mapping Java jar classes to behave
	like Python modules. It's meant to be mostly transparent and
	automagic.

	Provide a class_path_translation that will match the import path
	to a jar classpath.
	"""

	__metaclass__ = MetaModule

	_parent = None

	class_path_translation = re.compile("""
		(?P<path>.*)
		""", re.X)


	def __new__(cls):
		raise NotImplementedError("%s should be treated like a module. Please do not instantiate it." % cls.__name__)

	def __init__(cls):
		raise NotImplementedError("%s should be treated like a module. Please do not instantiate it." % cls.__name__)






class opencv(Antikythera):

	class_path_translation = re.compile("""
		""", re.X)


