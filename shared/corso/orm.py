"""
    Mapping helpers for persisting things with databases.

    PlasticORM - SimpleORMwasTakenORM
"""

import functools, textwrap
import sys

from shared.data.recordset import RecordSet

# MySQL connector implementation for PlasticORM
#import mysql.connector

# SQLite connector needs
import sqlite3

META_QUERIES = {
    None: {
        'insert': textwrap.dedent("""
            -- Insert from PlasticORM_Connection
            insert into %s
                (%s)
            values
                (%s)
            """),
        'update': textwrap.dedent("""
            -- Update from PlasticORM_Connection
            update %s
            set %s
            where %s
            """),
        'basic_filtered': textwrap.dedent("""
            -- A Basic filteres query for PlasticORM
            select %s
            from %s
            where %s
            """)
    },
    'MYSQL': {
        'primaryKeys': textwrap.dedent("""
                -- Query for primary keys for PlasticORM
                select c.COLUMN_NAME
                ,   case when c.extra like '%auto_increment%' 
                            then 1
                        else 0
                    end as autoincrements
                from information_schema.columns as c
                where lower(c.table_name) = lower(PARAM_TOKEN)
                    and c.column_key = 'PRI'
                    and lower(c.table_schema) = lower(PARAM_TOKEN)
                order by c.ordinal_position
                """),
        'columns': textwrap.dedent("""
                -- Query for column names for PlasticORM 
                select c.COLUMN_NAME,
                    case when c.IS_NULLABLE = 'NO' then 0
                        else 1
                    end as IS_NULLABLE
                from information_schema.columns as c
                where c.table_name = PARAM_TOKEN
                    and c.table_schema = PARAM_TOKEN
                order by c.ordinal_position
                """),
    },
    'SQLITE': {
        'primaryKeys': textwrap.dedent("""
                -- Query for primary keys for PlasticORM using SQLite3
                -- NOTE: requires additional processing!
                PRAGMA table_info(PARAM_TOKEN)
                """),
        'columns': textwrap.dedent("""
                -- Query for column names for PlasticORM using SQLite3
                -- NOTE: requires additional processing!
                PRAGMA table_info(PARAM_TOKEN)
                """),
    },
}


def isIgnition():
    try:
        _ = getattr(system, 'db')
        return True
    except:
        return False


class PlasticORM_Ignition(object):
    _engine = None
    _param_token = '?'
    
    def __init__(self, dbName):
        self.dbName = dbName
        self._engine = system.db.getConnectionInfo(self.dbName).getValueAt(0,'DBType')
        self.tx = None
        
    def __enter__(self):
        if self.tx == None:
            self.tx = system.db.beginTransaction(self.dbName)
        return self
    
    def __exit__(self, *args):
        if self.tx:
            system.db.commitTransaction(tx)
            system.db.closeTransaction(tx)
            self.tx = None
            
    def _execute_query(self, query, values):
        if self.tx:
            return RecordSet(initialData=system.db.runPrepQuery(query, values, self.dbName, self.tx))
        else:
            return RecordSet(initialData=system.db.runPrepQuery(query, values, self.dbName))
    
    def _execute_insert(self, insertQuery, insertValues):
        if self.tx:
            return system.db.runPrepUpdate(insertQuery, insertValues, self.dbName, self.tx, getKey=1)
        else:
            return system.db.runPrepUpdate(insertQuery, insertValues, self.dbName, getKey=1)

    def _execute_update(self, updateQuery, updateValues):
        if self.tx:
            system.db.runPrepUpdate(updateQuery, updateValues, self.dbName, self.tx, getKey=0)
        else:
            system.db.runPrepUpdate(updateQuery, updateValues, self.dbName, getKey=0)


class PlasticORM_MySQL(object):
    _engine = 'MYSQL'
    _param_token = '%s'
    
    MYSQL_CONNECTION_CONFIG = dict(
        host='mysql8-test.corso.systems',
        port='31825',
        database='test',
        user='root',
        password='********',
        use_pure=True,
        autocommit=True,
        auth_plugin='mysql_native_password',
    )
    
    def __init__(self, configDict=None):
        self.config = configDict or self.MYSQL_CONNECTION_CONFIG
        self.connection = None
        
    def __enter__(self):
        if self.connection == None:
            self.connection = mysql.connector.connect(**self.config)
        return self
    
    def __exit__(self, *args):
        if not self.connection == None:
            # Commit changes before closing
            if not self.connection.autocommit:
                self.connection.commit()
            self.connection.close()
            self.connection = None
    
    # Override these depending on the DB engine
    def _execute_query(self, query, values):
        """Execute a query. Returns rows of data."""
        with self as plasticDB:
            cursor = plasticDB.connection.cursor()
            cursor.execute(query,params=values)
            rs = RecordSet(initialData=cursor.fetchall(), recordType=cursor.column_names)
        return rs    
    
    def _execute_insert(self, insertQuery, insertValues):
        """Execute an insert query. Returns an integer for the row inserted."""
        with self as plasticDB:
            cursor = plasticDB.connection.cursor()
            cursor.execute(insertQuery,params=insertValues)
            return cursor.lastrowid
        
    def _execute_update(self, updateQuery, updateValues):
        """Execute an updated query. Returns nothing."""
        with self as plasticDB:
            cursor = plasticDB.connection.cursor()
            cursor.execute(updateQuery,params=updateValues)


class PlasticORM_SQLite3(object):
    _engine = 'SQLITE'
    _param_token = '?'
    
    
    def __init__(self, dbFile=':memory:'):
        self.config = dbFile
        self.connection = None
        
    def __enter__(self):
        if self.connection == None:
            self.connection = sqlite3.connect(self.config)
        return self
    
    def __exit__(self, *args):
        if not self.connection == None:
            # Commit changes before closing (sqlite doesn't autocommit)
            self.connection.commit()
            self.connection.close()
            self.connection = None
    
    # Override these depending on the DB engine
    def _execute_query(self, query, values):
        """Execute a query. Returns rows of data."""
        with self as plasticDB:
            cursor = plasticDB.connection.cursor()
            cursor.execute(query,values)
            rs = RecordSet(initialData=cursor.fetchall(), recordType=zip(*cursor.description)[0])
        return rs    
    
    def _execute_insert(self, insertQuery, insertValues):
        """Execute an insert query. Returns an integer for the row inserted."""
        with self as plasticDB:
            cursor = plasticDB.connection.cursor()
            cursor.execute(insertQuery, insertValues)
            return cursor.lastrowid
        
    def _execute_update(self, updateQuery, updateValues):
        """Execute an updated query. Returns nothing."""
        with self as plasticDB:
            cursor = plasticDB.connection.cursor()
            cursor.execute(updateQuery, updateValues)

    # SQLite retrieves these a bit differently...
    def primaryKeys(self, schema, table):
        """PK and autoincrement"""
        pkQuery = self._get_query_template('primaryKeys')
        pkQuery = pkQuery.replace('?', table) # can't var a pragma...
        results = self.query(pkQuery, [])
        pkCols = []
        for row in results:
            if row['pk']:                  # sqlite autoincrements int primary keys
                pkCols.append( (row['name'], 1 if row['type'] == 'integer' else 0) )
        return RecordSet(initialData=pkCols, recordType=('COLUMN_NAME', 'autoincrements'))

    def columnConfig(self, schema, table):
        columnQuery = self._get_query_template('columns')
        columnQuery = columnQuery.replace('?', table) # can't var a pragma...
        results = self.query(columnQuery, [])
        cols = []
        for row in results:
            cols.append( (row['name'], not row['notnull']) )
        return RecordSet(initialData=cols, recordType=('COLUMN_NAME', 'IS_NULLABLE'))


class _Template_PlasticORM_Connection(object):
    """Enables mixins to be properly error'd if missing methods."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("DB engines should be made as a mixin.")
        
    def __enter__(self):
        raise NotImplementedError("DB engines should be made as a mixin.")
        return self
    
    def __exit__(self, *args):
        raise NotImplementedError("DB engines should be made as a mixin.")
    
    def _execute_query(self, query, values):
        raise NotImplementedError("DB engines should be made as a mixin.")

    def _execute_insert(self, insertQuery, insertValues):
        raise NotImplementedError("DB engines should be made as a mixin.")

    def _execute_update(self, updateQuery, updateValues):
        raise NotImplementedError("DB engines should be made as a mixin.")

    def primaryKeys(self, schema, table):
        pkQuery = self._get_query_template('primaryKeys')
        return self.query(pkQuery, [table, schema])

    def columnConfig(self, schema, table):
        columnQuery = self._get_query_template('columns')
        return self.query(columnQuery, [table, schema])


class MetaPlasticORM_Connection(type):
    
    def __new__(cls, clsname, bases, attributes):
        if isIgnition():
            print 'PlasticORM setting up on Ignition interfaces'
            bases = (PlasticORM_Ignition,) + bases
        elif 'sqlite3' in sys.modules:
            print 'PlasticORM setting up on SQLite'
            bases = (PlasticORM_SQLite3,) + bases
        elif 'mysql' in sys.modules:
            print 'PlasticORM setting up on MySQL'
            bases = (PlasticORM_MySQL,) + bases
            
        return super(MetaPlasticORM_Connection,cls).__new__(cls, clsname, bases, attributes)


class PlasticORM_Connection(_Template_PlasticORM_Connection):
    """Helper class for connecting to the database.
    Replace and override as needed.
    """
    __metaclass__ = MetaPlasticORM_Connection
            
    def dumpCore(function):
        @functools.wraps(function)
        def handle_error(self,*args,**kwargs):
            try:
                return function(self,*args,**kwargs)
            except Exception as error:
                print 'DB Error: ', str(error)
                if args:
                    print 'Arguments: ', args
                if kwargs:
                    print 'Key word arguments: ', kwargs
                raise error
        return handle_error
    
    def _get_query_template(self, queryType):
        qt = META_QUERIES[self._engine].get(queryType) or META_QUERIES[None][queryType]
        return qt.replace('PARAM_TOKEN',self._param_token)
    
    @dumpCore
    def query(self,query,params=[]):
        query = query.replace('PARAM_TOKEN', self._param_token)
        return self._execute_query(query,params)

    def queryOne(self,query,params=[]):
        return self.query(query,params)[0]

    @dumpCore
    def insert(self, table, columns, values):
        insertQuery = self._get_query_template('insert')
        insertQuery %= (table, 
                        ','.join(columns), 
                        ','.join([self._param_token]*len(values)))
        
        insertQuery = insertQuery.replace('PARAM_TOKEN', self._param_token)
        return self._execute_insert(insertQuery,values)
    
    @dumpCore
    def update(self, table, setDict, keyDict):
        setColumns,setValues = zip(*sorted(setDict.items()))
        keyColumns,keyValues = zip(*sorted(keyDict.items()))
        
        updateQuery = self._get_query_template('update')
        updateQuery %= (table, 
                        ','.join('%s=%s' % (setColumn, self._param_token)
                                 for setColumn 
                                 in setColumns), 
                        '\n\t and '.join('%s=%s' % (keyColumn, self._param_token)
                                         for keyColumn 
                                         in keyColumns))
        
        updateQuery = updateQuery.replace('PARAM_TOKEN', self._param_token)
        self._execute_update(updateQuery, setValues+keyValues)


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
            
            # We break slicing semantics a bit here so that we can cover all cases inclusively
            # Between is inclusive, so 'at least' and 'up to' should be exclusive.
            # That way you can apply all three and get all combinations
            elif selector.start is not None and selector.stop is not None:
                return ' (%s between PARAM_TOKEN and PARAM_TOKEN) ' % self.fqn, (self.dereference(selector.start), self.dereference(selector.stop))
            elif selector.start is None:
                return ' (%s < PARAM_TOKEN) ' % self.fqn, (self.dereference(selector.stop),)
            elif selector.stop:
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


class MetaPlasticORM(type):
    """Metaclass that allows new PlasticORM classes to autoconfigure themselves.
    """
    def __new__(cls, clsname, bases, attributes):        
        return super(MetaPlasticORM,cls).__new__(cls, clsname, bases, attributes)
    
    def __init__(cls, clsname, bases, attributes):
        # Do a null setup for the base class
        if clsname == 'PlasticORM':
            cls._table = ''
        else:
            cls._table = cls._table or clsname
            cls._table = cls._table.lower()
            cls._verify_columns()
        cls._pending = []
        
        for ix,column in enumerate(cls._columns):
            setattr(cls,column,PlasticColumn(cls, column))
                        
        return super(MetaPlasticORM,cls).__init__(clsname, bases, attributes)   

    def _verify_columns(cls):
                
        if cls._autoconfigure or not (cls._primary_key_cols and cls._primary_key_auto):
            with PlasticORM_Connection(cls._dbInfo) as plasticDB:
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
                            
            
class PlasticORM(object):
    """Base class that connects a class to the database.

    When declaring the subclass, set the defaults to persist them.

    NOTE: If no columns are configured, the class will attempt to autoconfigure
      regardless of whether _autoconfigure is set.
    """
    __metaclass__ = MetaPlasticORM
    
    # set defaults for derived classes here
    _dbInfo = None

    _autocommit = False
    _autoconfigure = False
    _table = ''
    _schema = None
    _columns = tuple()
    _primary_key_cols = tuple()
    _primary_key_auto = tuple()
    _non_null_cols = tuple()
    
    _pending = False
    
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
            
        super(PlasticORM,self).__setattr__(attribute, value)
        
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
        
        with PlasticORM_Connection(cls._dbInfo) as plasticDB:
            
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
        
        with PlasticORM_Connection(self._dbInfo) as plasticDB:
            
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
        
        with PlasticORM_Connection(self._dbInfo) as plasticDB:
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
        
        with PlasticORM_Connection(self._dbInfo) as plasticDB:
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