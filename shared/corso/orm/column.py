

class PlasticColumn(object):
    __slots__ = ('_parent', '_column')
    

    def __init__(self, parentClass, columnName):
        # anchor to the parent class to ensure runtime modifications are considered
        self._parent = parentClass
        self._column = columnName
    

    def dereference(self, selector):
        if isinstance(selector, PlasticColumn):
            return selector.fqn
        else:
            return selector


    @property
    def fullyQualifiedIdentifier(self):
        if self._parent._schema:
            return '%s.%s.%s' % (self._parent._schema, self._parent._table, self._column)
        else:
            return '%s.%s' % (self._parent._table, self._column)
    

    @property
    def fqn(self):
        return self.fullyQualifiedIdentifier
    

    def __getitem__(self, selector):
        if isinstance(selector, slice):
            if selector.step:
                raise NotImplementedError("No mapping to step exists yet.")
            
            elif selector.start is None and selector.stop is None:
                return self.isNotNull()
            
            # We break slicing semantics a bit here so that we can cover all cases inclusively
            # Between is inclusive, so 'at least' and 'up to' should be exclusive.
            # That way you can apply all three and get all combinations
            
            elif selector.start is not None and selector.stop is not None:
                return ' (%s between PARAM_TOKEN and PARAM_TOKEN) ' % self.fqn, (self.dereference(selector.start), self.dereference(selector.stop))
            
            elif selector.start is None:
                return ' (%s < PARAM_TOKEN) ' % self.fqn, (self.dereference(selector.stop),)
            
            elif selector.stop is None:
                return ' (%s > PARAM_TOKEN) ' % self.fqn, (self.dereference(selector.start),)
        
        elif isinstance(selector, (tuple,list)):
            if len(selector) == 1:
                return ' (%s = PARAM_TOKEN) ' % self.fqn, (self.dereference(selector),)
            
            else:
                return ' (%s in (%s)) ' % (self.fqn, ','.join(['PARAM_TOKEN']*len(selector))), tuple(selector)
        
        else:
            return ' (%s = PARAM_TOKEN) ' % self.fqn, (self.dereference(selector),)
    

    def isNull(self):
        return ' (%s is null) ' % self.fqn, tuple()

        
    def isNotNull(self):
        return ' (not %s is null) ' % self.fqn, tuple()
    

    def __bool__(self):
        # Always appear like None when not in comparisons
        return None