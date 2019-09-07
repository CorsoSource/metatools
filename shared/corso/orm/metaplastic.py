

from .connection import PlasticORM_Connection_Base
from .column import PlasticColumn


class MetaPlasticORM(type):
    """Metaclass that allows new PlasticORM classes to autoconfigure themselves.
    """
    def __new__(cls, clsname, bases, attributes):        
        return super(MetaPlasticORM,cls).__new__(cls, clsname, bases, attributes)
    
    
    def __init__(cls, clsname, bases, attributes):
        # Do a null setup for the base classes
        if clsname.startswith('Plastic') or cls._connectionType==PlasticORM_Connection_Base:
            cls._table = ''
        else:
            # Derived classes get initialized, though.
            # Thus, be sure to configure _before_ creating the derived classes
            cls._connection = cls._connectionType(cls._dbInfo)
            cls._table = cls._table or clsname
            cls._table = cls._table.lower()
            cls._verify_columns()
        cls._pending = []
        
        for ix,column in enumerate(cls._columns):
            setattr(cls,column,PlasticColumn(cls, column))
                        
        return super(MetaPlasticORM,cls).__init__(clsname, bases, attributes)   


    def _verify_columns(cls):
                
        if cls._autoconfigure or not (cls._primary_key_cols and cls._primary_key_auto):
            with cls._connection as plasticDB:
                pkCols = plasticDB.primaryKeys(cls._schema, cls._table)
                if pkCols:
                    cls._primary_key_cols, cls._primary_key_auto = zip(*(r._tuple for r in pkCols))    
        
        if cls._autoconfigure or not cls._columns:
            columns = plasticDB.columnConfig(cls._schema, cls._table)
            if columns:
                cls._columns, cls._non_null_cols = zip(*[r._tuple for r in columns])
                # change to column names
                cls._non_null_cols = tuple(col 
                                           for col,nullable 
                                           in zip(cls._columns, cls._non_null_cols)
                                           if nullable
                                          )
                cls._values = [None]*len(cls._columns)
            else:
                cls._columns = tuple()
                cls._non_null_cols = tuple()
                cls._values = []
                            