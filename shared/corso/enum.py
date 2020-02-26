"""A simple enumeration class.
"""

class MetaEnum(type):
    
    _initFields = ('_fields', '_values')
    
    def __init__(cls, clsname, bases, attributes):
        
        fvs = [(key,value) for key, value in attributes.items() if not key.startswith('_')]
        
        if fvs:
            fields,values = zip(*sorted(fvs, key=lambda (key,value): value))
        
            setattr(cls, '_fields', fields)
            setattr(cls, '_values', values)
        else:
            setattr(cls, '_fields', tuple())
            setattr(cls, '_values', tuple())

        
        def __setattr__readonly__(self, key, _):
            raise AttributeError("<%s> attributes are readonly" % clsname)
                
    def __setattr__(cls, key, value):

        if key in cls._initFields:
            # Allow modification for the metaclass __init__
            try:
                if getattr(cls, key):
                    raise AttributeError("<%s>'s %s is not to be changed once created.'" % (cls.__name__, key))
                    
                # ... but once the class is initialized, then do _not_ allow modification
                else:
                    super(MetaEnum, cls).__setattr__(key, value)

            # ... but once the class is initialized, then do _not_ allow modification
            except AttributeError:
                super(MetaEnum, cls).__setattr__(key, value)
        elif key.startswith('_'):
            raise AttributeError("<%s> class attributes are readonly" % cls.__name__)
        else:
            raise AttributeError("<%s> attributes are readonly" % cls.__name__)
                
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