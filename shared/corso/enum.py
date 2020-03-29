"""A simple enumeration class.
"""


__copyright__ = """Copyright (C) 2020 Corso Systems"""
__license__ = 'Apache 2.0'
__maintainer__ = 'Andrew Geiger'
__email__ = 'andrew.geiger@corsosystems.com'

__all__ = ['Enum']


class MetaEnumValue(type):
	
	def __init__(cls, clsname, bases, attributes):
		for base in bases:
			if base.__name__ is not 'EnumValue':
				setattr(cls, '_type', base)
				break
		
		def __setattr__readonly__(self, key, _):
			raise AttributeError("<%r> is readonly" % self)
		setattr(cls, '__setattr__', __setattr__readonly__)

		
class EnumValue(object):
	_parent = None
	_type = None
		
	# def __str__(self):
	#     return '%s.%s' % (self._parent.__name__, self.__class__.__name__)

	def __repr__(self):
		return '<%s.%s %s>' % (self._parent.__name__, 
							   self.__class__.__name__, 
							   self._type.__str__(self))
	

	
class MetaEnum(type):
	
	_initFields = ('_fields', '_values')
	_class_initialized = False
		
	def __init__(cls, clsname, bases, attributes):
		
		super(MetaEnum, cls).__setattr__('_class_initialized', False) # bypass interlock
		
		fvs = [(key,value) for key, value in attributes.items() if not key.startswith('_')]
		
		if fvs:
			fields,values = zip(*sorted(fvs, key=lambda (key,value): value))
		
			setattr(cls, '_fields', fields)
			setattr(cls, '_values', values)
			
			for key,value in fvs:
				EnumAttribute = MetaEnumValue(key, (EnumValue,type(value)), {'_parent': cls})
				setattr(cls, key, EnumAttribute(value))

			
		else:
			setattr(cls, '_fields', tuple())
			setattr(cls, '_values', tuple())
		
		cls._class_initialized = True
				
			
	def __setattr__(cls, key, value):
		if cls._class_initialized:
			raise AttributeError("<%s> attributes are readonly" % cls.__name__)
		else:
			super(MetaEnum, cls).__setattr__(key, value)                
				
	def __contains__(cls, enum_key):
		return enum_key in cls._fields
	
	def keys(cls):
		return cls._fields

	def values(cls):
		return cls._values

	def __iter__(cls):
		return iter(getattr(cls, field) for field in cls._fields)
	
	def __getitem__(cls, attribute):
		return getattr(cls, attribute)
	
	def __str__(cls):
		return cls.__name__
	
	def __repr__(cls):
		return "<%s {%s}>" % (cls.__name__, ', '.join("%s: %s" % (repr(key), repr(value)) for key, value in cls))

	
class Enum(object):
	__metaclass__ = MetaEnum
	__slots__ = tuple()
		
	_fields = tuple()
	_values = tuple()
	
	def __new__(cls, value=None):
		if value is not None and value in cls._values:
			return getattr(cls, cls._fields[cls._values.index(value)])
		raise NotImplementedError("%s is an enumeration and does not support instantiation." % cls.__name__) 
	
	def __init__(cls):
		raise NotImplementedError("%s is an enumeration and does not support instantiation." % cls.__name__)
		
	def __setattr__(cls, key, value):
		raise AttributeError("<%s> attributes are readonly" % cls.__name__)
