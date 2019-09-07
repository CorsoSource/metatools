

import functools

from shared.data.recordset import RecordSet
from .metaplastic import MetaPlasticORM
from .connection import PlasticORM_Connection_Base

            
class PlasticORM_Base(object):
    """Base class that connects a class to the database.

    When declaring the subclass, set the defaults to persist them.

    NOTE: If no columns are configured, the class will attempt to autoconfigure
      regardless of whether _autoconfigure is set.
    """
    __metaclass__ = MetaPlasticORM
    
    # set defaults for derived classes here
    _connectionType = PlasticORM_Connection_Base
    _connection = None
    _dbInfo = None

    _autocommit = False
    _autoconfigure = False
    _table = ''
    _schema = None
    _columns = tuple()
    _primary_key_cols = tuple()
    _primary_key_auto = tuple()
    _non_null_cols = tuple()
    
    _pending = []
    

    def _delayAutocommit(function):
        @functools.wraps(function)
        def resumeAfter(self, *args, **kwargs):
            try:
                bufferAutocommit = self._autocommit
                self._autocommit = False
                return function(self, *args, **kwargs)
            finally:
                self._autocommit = bufferAutocommit
        return resumeAfter
    

    @_delayAutocommit
    def __init__(self, *args, **kwargs):
        """Initialize the object with the given values.
        If key columns are given, then pull the rest.
        """
        values = dict((col,val) for col,val in zip(self._columns,args))
        values.update(kwargs)
        
        if kwargs.get('_bypass_validation', False):
            for column,value in values.items():
                setattr(self, column, value)
            self._pending = []
        else:
            if all(key in values for key in self._primary_key_cols):
                self._retrieveSelf(values)
            
            for column,value in values.items():
                setattr(self, column, value)
            
    
    def __setattr__(self, attribute, value):
        if attribute in self._columns and getattr(self, attribute) <> value:
            self._pending.append(attribute)
            
        super(PlasticORM_Base,self).__setattr__(attribute, value)
        
        if self._autocommit and self._pending:
            self._commit()


    @property
    def _autoKeyColumns(self):
        return set(pkcol 
                   for pkcol,auto
                   in zip(self._primary_key_cols, self._primary_key_auto)
                   if auto)
    

    @property
    def _nonAutoKeyColumns(self):
        return set(pkcol 
                   for pkcol,auto
                   in zip(self._primary_key_cols, self._primary_key_auto)
                   if not auto)
    

    @property
    def _nonKeyColumns(self):
        return set(self._columns).difference(self._primary_key_cols)


    @classmethod
    @_delayAutocommit
    def find(cls, *filters):
        
        filters,values = zip(*filters)
        values = [value 
                  for conditionValues in values
                  for value in conditionValues]
        
        with cls._connection as plasticDB:
            
            recordsQuery = plasticDB._get_query_template('basic_filtered')
            recordsQuery %= (
                ','.join(cls._columns),
                cls._table,
                '\n\t and '.join(condition for condition in filters)
                )
            
            records = plasticDB.query(recordsQuery, values)
        
        objects = []
        for record in records:
            initDict = record._asdict()
            initDict['_bypass_validation'] = True
            objects.append(cls(**initDict))

        return objects
        
        
    @_delayAutocommit
    def _retrieveSelf(self, values=None):
        if values:
            keyDict = dict((key,values[key]) 
                           for key 
                           in self._primary_key_cols)
        else:
            keyDict = dict((key,getattr(self,key)) 
                           for key 
                           in self._primary_key_cols)
            
        if any(value is None or isinstance(value, PlasticColumn)
               for value 
               in keyDict.values()):
            raise ValueError('Can not retrieve record missing key values: %s' % 
                             ','.join(col 
                                      for col 
                                      in keyDict 
                                      if keyDict[key] is None))
        
        with self._connection as plasticDB:
            
            keyColumns,keyValues = zip(*sorted(keyDict.items()))

            recordQuery = plasticDB._get_query_template('basic_filtered')
            recordQuery %= (
                ','.join(sorted(self._nonKeyColumns)),
                self._table,
                ','.join('%s = %%s' % keyColumn 
                         for keyColumn 
                         in sorted(keyColumns)))

            entry = plasticDB.queryOne(recordQuery, keyValues)    
            
            for column in self._nonKeyColumns:
                setattr(self, column, entry[column])
            
        self._pending = []
        
    
    def _insert(self):
        # Can't insert if we're missing non-null or non-auto key columns
        # Darn well shouldn't have a nullable key column, but compound keys
        #   can get silly.
        if set(self._non_null_cols).union(self._nonAutoKeyColumns).difference(self._pending):
            return
        
        # Don't insert the auto columns
        if self._primary_key_auto:
            columns = sorted(set(self._pending).difference(self._autoKeyColumns))
        else:
            columns = self._pending
        
        values = [getattr(self,column) for column in columns]
        
        with self._connection as plasticDB:
            rowID = plasticDB.insert(self._table, columns, values)
            # I can't think of a case where there's more than one autocolumn, but /shrug
            # they're already iterables, so I'm just going to hit it with zip
            for column in self._autoKeyColumns:
                setattr(self,column,rowID)
        
        self._pending = []
        
        
    def _update(self):
        # Don't update a column to null when it shouldn't be
        for column in set(self._non_null_cols).intersection(self._pending):
            if column is None:
                raise ValueError('Can not null column %s in table %s.%s' % (column, self._schema, self._table))

        setValues = dict((column,getattr(self,column))
                      for column 
                      in self._pending)
        
        keyValues = dict((keyColumn,getattr(self,keyColumn))
                         for keyColumn
                         in self._primary_key_cols)
        
        with self._connection as plasticDB:
            plasticDB.update(self._table, setValues, keyValues)
            
        self._pending = []

        
    def _commit(self):
        if not self._pending:
            return
        
        # Insert if we don't have the key values yet (at least one of )
        if not all(getattr(self, keyColumn) is not None 
                    and not isinstance(getattr(self, keyColumn), PlasticFilter)
                   for keyColumn 
                   in self._primary_key_cols):
            self._insert()
        else:
            self._update()
            
            
    def __repr__(self):
        return '%s(%s)' % (self._table, ','.join('%s=%s' % (col,repr(getattr(self,col)))
                                                 for col
                                                 in self._columns))