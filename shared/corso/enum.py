"""A simple enumeration class.
"""


class MetaEnumValue(type):
    
    def __init__(cls, clsname, bases, attributes):

        def __setattr__readonly__(self, key, _):
            raise AttributeError("<%r> is readonly" % self)
        
        setattr(cls, '__setattr__', __setattr__readonly__)

        
class EnumValue(int):
    __metaclass__ = MetaEnumValue
    _parent = None
    
    def __repr__(self):
        return '<%s.%s %s>' % (self._parent.__name__, self.__class__.__name__, self)

    
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
                EnumAttribute = MetaEnumValue(key, (EnumValue,), {'_parent': cls})
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
                
                
    def __iter__(cls):
        return iter(zip(cls._fields, cls._values))
    
    def __getitem__(cls, attribute):
        return getattr(cls, attribute)
    
    def __repr__(cls):
        return "{%s}" % ', '.join("%s: %s" % (repr(key), repr(value)) for key, value in cls)

    
class Enum(object):
    __metaclass__ = MetaEnum
    __slots__ = tuple()
        
    _fields = tuple()
    _values = tuple()
    
    def __new__(cls):
        raise NotImplementedError("%s is an enumeration and does not support instantiation." % cls.__name__)
    
    def __init__(cls):
        raise NotImplementedError("%s is an enumeration and does not support instantiation." % cls.__name__)
        
    def __setattr__(cls, key, value):
        raise AttributeError("<%s> attributes are readonly" % cls.__name__)