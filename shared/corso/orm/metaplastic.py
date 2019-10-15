

from .connection import PlasticORM_Connection_Base
from .column import PlasticColumn


class MetaPlasticORM(type):
    """Metaclass that allows new PlasticORM classes to autoconfigure themselves.

    When a new PlasticORM class is _created_ (not instantiated!), this will
      be run. On __init__ the new PlasticORM class will first 
    """
    def __new__(cls, clsname, bases, attributes): 
        # Placeholder.       
        return super(MetaPlasticORM,cls).__new__(cls, clsname, bases, attributes)
    
    
    def __init__(cls, clsname, bases, attributes):
        """Initializes the basic attributes for the class itself.
        Auto-configuration is kicked off here.
        """

        # Do a null setup for the base classes.
        # This allows Plastic to defer some of its configuration until the
        #   database specific classes are defined.
        if clsname.startswith('Plastic') or cls._connectionType==PlasticORM_Connection_Base:
            cls._table = ''

        # Derived classes get initialized, though.
        # Thus we can be sure to configure _before_ creating the derived classes
        else:
            # Critically, the connection definition is deferred until here
            cls._connection = cls._connectionType(cls._dbInfo)
            cls._table = cls._table or clsname
            cls._table = cls._table.lower()
            cls._verify_columns()
        cls._pending = []
        
        # Add the column names themselves as convenience attributes.
        # These are of type PlasticColumn and allow some additional abstractions.
        # NOTE: columns are not validated! They are assumed to not include
        #   spaces or odd/illegal characters.
        for ix,column in enumerate(cls._columns):
            setattr(cls,column,PlasticColumn(cls, column))
        
        # Continue and carry out the normal class definition process   
        return super(MetaPlasticORM,cls).__init__(clsname, bases, attributes)   


    def _verify_columns(cls):
        """Auto-configure the class definition. 

        As instances are created, they all follow the schema that is retrieved,
          so this only needs to be done once, so we perform it on class definition.
        """

        # Auto-configure the key columns, if needed        
        if cls._autoconfigure or not (cls._primary_key_cols and cls._primary_key_auto):
            with cls._connection as plasticDB:
                # collect the PKs from the engine
                pkCols = plasticDB.primaryKeys(cls._schema, cls._table)
                if pkCols:
                    cls._primary_key_cols, cls._primary_key_auto = zip(*(r._tuple for r in pkCols))    
        
        # Auto-configure the columns, if needed
        if cls._autoconfigure or not cls._columns:
            with cls._connection as plasticDB:
                # collect the columns from the engine
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
                            