"""
    Lock Out - Tag Out
    Hotpatch access to even the most inappropriate things.
    
    WARNING: It can NOT be emphasized enough how much
             this breaks the class model contracts of
             Java itself. 
             
    Use this for monkey-patching things in the most impatient way.
"""
from shared.tools.logging import Logger

from java.lang import Class as JavaClass, Object as JavaObject, NoSuchFieldException
from java.lang.reflect import Field, Modifier

_FieldModifiers = Field.getDeclaredField('modifiers')


class LOTO(object):
    """Context manager to safely adjust field properties.
    
    WARNING: this is "as possible", not _actually_ safe.
             Using this is safer because it will automatically
             put the field back to it's original configuration.
             
    NOTE: If the same flag is set for both enable and disable, the
          enabled flag will win. 
    """
    def __init__(self, obj, field_name_to_unlock, 
                 flags_to_disable=0, flags_to_enable=0):
                 
        Logger().info('init...')
        
        # check if we're targetting the class or an instance of it
        if isinstance(obj, JavaClass):
            self.instance = None
            self.clazz = obj
        else:
            self.instance = obj
            self.clazz = obj.getClass()
        
        self.field_name = field_name_to_unlock
        self.field = None
        
        self.resolve_field()
        
        self.flags_to_disable = flags_to_disable
        self.flags_to_enable = flags_to_enable
        
        self.originally_accessible = self.field.isAccessible()
        self.original_modifiers = self.field.getModifiers()
    
        
    # context management
    def __enter__(self):
        self.unlock()
#       return self
        if self.instance:
            return self.field.get(self.instance)
        else:
            return self.field.get(self.clazz)
        
    def __exit__(self, ex_type, ex_value, ex_traceback):
        self.relock()
        

    def resolve_field(self):
        
        Logger().info('resolving field...')
        
        clazz = self.clazz
        field = None
        i = 10
        while i and clazz is not JavaObject:
            try:
                field = clazz.getDeclaredField(self.field_name)
            except NoSuchFieldException:
                Logger().info('... %(clazz)r')
                clazz = clazz.getSuperclass()
                
            i-=1
        Logger().info('...[%(i)d] ended on %(clazz)r...')
        if field is None:
            raise AttributeError('Field %r not found in the class inheritance structure of %r!' % (self.field_name, self.clazz,))
                
        Logger().info('field: %(field)r')

        self.field = field

    def unlock(self):
    
        Logger().info('Unlocking...')

        # allow field modifications
        _FieldModifiers.setAccessible(True)
        
        # unlock for modification
        if not self.originally_accessible:
            self.field.setAccessible(True)
        
        # modify!
        new_modifiers = self.original_modifiers
        new_modifiers &= ~self.flags_to_disable
        new_modifiers |= self.flags_to_enable
        _FieldModifiers.setInt(self.field, new_modifiers)

        Logger().info('Done...')


    def relock(self):
        try:
            # allow field modifications
            _FieldModifiers.setAccessible(True)
            
            # revert modifications
            _FieldModifiers.setInt(self.field, self.original_modifiers)
            
            # relock, if needed
            if self.field.isAccessible() != self.originally_accessible:
                self.field.setAccessible(self.originally_accessible)
        finally:
            # resume lockout
            _FieldModifiers.setAccessible(False)
            



#The Modifier flags available (and their enum value as of writing this) 
#        ABSTRACT   1024
#           FINAL   16
#       INTERFACE   512
#          NATIVE   256
#         PRIVATE   2
#       PROTECTED   4
#          PUBLIC   1
#          STATIC   8
#          STRICT   2048
#    SYNCHRONIZED   32
#       TRANSIENT   128
#        VOLATILE   64

for name in dir(Modifier):
    if name == name.upper():
        value = getattr(Modifier, name)
        if isinstance(value, int):
            setattr(LOTO, name, value)