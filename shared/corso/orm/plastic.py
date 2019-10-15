

import functools

from shared.data.recordset import RecordSet
from .metaplastic import MetaPlasticORM
from .connection import PlasticORM_Connection_Base

            
class PlasticORM_Base(object):
    """Base class that connects a derived class to the database.

    When declaring the subclass, set the defaults in it directly 
      to avoid the overhead of auto-configuring.

    NOTE: If no columns are configured, the class will attempt to autoconfigure
      regardless of whether _autoconfigure is set.
    """
    __metaclass__ = MetaPlasticORM
    
    # set defaults for derived classes here
    
    # By default this is a nop. Be sure to set this is the 
    #   engine-specific derived class
    _connectionType = PlasticORM_Connection_Base
    _connection = None
    _dbInfo = None

    # Set _autocommit to True to have changes to the instaces immediately applied
    _autocommit = False
    
    # Set _autoconfigure to True to force the class to reconfigure every time
    # NOTE: if there are no columns or PKs defined, auto-configure runs regardless
    _autoconfigure = False

    # Configure these to avoid auto-configure overhead
    _columns = tuple()
    _primary_key_cols = tuple()
    _primary_key_auto = tuple()
    _non_null_cols = tuple()
    
    # If the _table is blank, the class name will be used instead.
    _table = ''

    # Be sure to set the _schema. This is does not default!
    _schema = None
    
    # Holding list for queuing the changes that need to be applied
    _pending = []
    

    def _delayAutocommit(function):
        """During some internal housekeeping, it's handy to prevent Plastic to trying to
        apply changes part-way through.
        """
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
    def __init__(self, *args, bypass_validation=False, **kwargs):
        """Initialize the object's instance with the given values.

        Arguments are assumed to map directly in order to the columns.
        Key word arguments are applied over the arguments, if there's overlap.

        If key columns are given, then pull the rest unconfigured.

        Include the keyword arguement _bypass_validation = True
          to accept the values 
        """
        values = dict((col,val) for col,val in zip(self._columns,args))
        values.update(kwargs)
        
        # Take whatever yer given and like it
        if bypass_validation:
            for column,value in values.items():
                setattr(self, column, value)
            self._pending = []
        else:
            # Check if the keys are given, if so get all the values for that record
            if all(key in values for key in self._primary_key_cols):
                self._retrieveSelf(values)
            
            #... but then immediately override with the values provided
            for column,value in values.items():
                setattr(self, column, value)
            
    
    def __setattr__(self, attribute, value):
        """Do the autocommit bookkeeping, if needed"""

        # Set columns as pending changes
        if attribute in self._columns and getattr(self, attribute) != value:
            self._pending.append(attribute)
            
        super(PlasticORM_Base,self).__setattr__(attribute, value)
        
        # Note that this means setting _autocommit to True will
        #  IMMEDIATELY commit any pending changes!  
        if self._autocommit and self._pending:
            self._commit()


    @property
    def _autoKeyColumns(self):
        """Helper function for getting the key set"""
        return set(pkcol 
                   for pkcol,auto
                   in zip(self._primary_key_cols, self._primary_key_auto)
                   if auto)
    

    @property
    def _nonAutoKeyColumns(self):
        """Helper function for getting the non-autoincrement functions"""
        return set(pkcol 
                   for pkcol,auto
                   in zip(self._primary_key_cols, self._primary_key_auto)
                   if not auto)
    

    @property
    def _nonKeyColumns(self):
        """Helper function for getting the non-PK columns"""
        return set(self._columns).difference(self._primary_key_cols)


    @classmethod
    @_delayAutocommit
    def find(cls, *filters):
        """Return a list of instances for all the records that match the filters.

        The filters args is most easily generated as a sequence of PlasticColumn slices.
          PlasticColumn slicing returns a tuple of filter string and values to apply.
          Importantly, the values are applied as parameters.

        Filters can be applied by slicing a PlasticColumn.
          For example, to get records on a table with an ID column...
          ... between 4 and 10 (inclusive),
            Table.find(Table.ID[4:10])
          ... less than 5 (exclusive)
            Table.find(Table.ID[:5])
          ... greater than 12
            Table.find(Table.ID[12:])
          ... Column3 equals 'asdf'
            Table.find(Table.Column3['asdf'])
          ... ID is 3,4, or 7
            Table.find(Table.ID[3,4,7])
          ... ColumnA is the same as ColumnB 
              (this is... unlikely to be used, but it works as a consequence of the design)
            Table.find(Table.ColumnA[Table.ColumnB])

        NOTE: The slicing is NOT exactly the same semantically to normal list slicing.
          This is to simplify and be easier to analogue to SQL
        """
        # Split out the filter strings to use in the where clause
        #   and the values that are needed to be passed in as parameters
        filters,values = zip(*filters)
        values = [value 
                  for conditionValues in values
                  for value in conditionValues]
        
        with cls._connection as plasticDB:
            # Build the query string (as defined by the engine configured)
            recordsQuery = plasticDB._get_query_template('basic_filtered')
            recordsQuery %= (
                ','.join(cls._columns),
                cls._table,
                '\n\t and '.join(condition for condition in filters)
                )
            
            records = plasticDB.query(recordsQuery, values)
        
        # Render the results into a list 
        objects = []
        for record in records:
            initDict = record._asdict()
            initDict['_bypass_validation'] = True
            objects.append(cls(**initDict))

        return objects
        
        
    @_delayAutocommit
    def _retrieveSelf(self, **primaryKeyValues):
        """Automatically fill in the column values for given PK record."""
        # primaryKeyValues is a dict with a value for each PK
        if primaryKeyValues:
            keyDict = dict((key,primaryKeyValues[key]) 
                           for key 
                           in self._primary_key_cols)
        else:
            keyDict = dict((key,getattr(self,key)) 
                           for key 
                           in self._primary_key_cols)
        
        # Essentially assert that all PKs are set
        if any(value is None or isinstance(value, PlasticColumn)
               for value 
               in keyDict.values()):
            raise ValueError('Can not retrieve record missing key values: %s' % 
                             ','.join(col 
                                      for col 
                                      in keyDict 
                                      if keyDict[key] is None))
        
        # Query for associated record
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
        
        # Clear the pending buffer, since we just retrieved    
        self._pending = []
        
    
    def _insert(self):
        """Insert the current object's values as a new record.
        Can't insert if we're missing non-null or non-auto key columns
        (Darn well shouldn't have a nullable key column, but compound keys
          can get silly.)
        """
        # Don't attempt to insert if there aren't enough pending column values set
        #   to cover the required non-NULL columns (excluding auto key columns, since they, well, auto)
        if set(self._non_null_cols).union(self._nonAutoKeyColumns).difference(self._pending):
            return
        
        # Don't insert the auto columns
        if self._primary_key_auto:
            columns = sorted(set(self._pending).difference(self._autoKeyColumns))
        else:
            columns = self._pending
        
        # Collect the values from the object
        values = [getattr(self,column) for column in columns]
        
        # Delegate the insert to the engine and apply
        with self._connection as plasticDB:
            rowID = plasticDB.insert(self._table, columns, values)
            # I can't think of a case where there's more than one autocolumn, but /shrug
            # they're already iterables, so I'm just going to hit it with zip
            for column in self._autoKeyColumns:
                setattr(self,column,rowID)
        
        # Clear the pending buffer, since we just sync'd
        self._pending = []
        
        
    def _update(self):
        """Update the current object's record with the changed (pending) values.
        This will also do some minor validation to make sure it's compliant.
        """
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
        
        # Delegate the update to the engine and apply
        with self._connection as plasticDB:
            plasticDB.update(self._table, setValues, keyValues)
        
        # Clear the pending buffer, since we just sync'd
        self._pending = []

        
    def _commit(self):
        """Apply the changes, if any."""
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