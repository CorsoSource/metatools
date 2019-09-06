"""
	Mapping helpers for persisting things with databases.

	StORM - SimpleORMwasTakenORM
"""

import functools, textwrap

from shared.data.recordset import RecordSet

# MySQL connector implementation for StORM
import mysql.connector

MYSQL_CONNECTION_CONFIG = dict(
    host='mysql8-test.corso.systems',
    port='31825',
    database='test',
    user='root',
    password='hunter2',
    use_pure=True,
    autocommit=True,
)

class StORM_Connection(object):
    """Helper class for connecting to the database.
	Replace and override as needed.
    """
    def __init__(self, config=MYSQL_CONNECTION_CONFIG):
        self.config = config
        self.connection = None
        
    def __enter__(self):
        if self.connection == None:
            self.connection = mysql.connector.connect(**self.config)
        return self
    
    def __exit__(self, *args):
        if not self.connection == None:
            self.connection.close()
            self.connection = None
            
    def dumpCore(function):
        @functools.wraps(function)
        def handle_error(self,*args,**kwargs):
            try:
                return function(self,*args,**kwargs)
            except mysql.connector.ProgrammingError as error:
                print 'MySQL Error: ', str(error)
                if args:
                    print 'Arguments: ', args
                if kwargs:
                    print 'Key word arguments: ', kwargs
                    
                raise error
        return handle_error
    
    
    @dumpCore
    def query(self,q,p=[]):
        with self as c:
            cursor = c.connection.cursor()
            cursor.execute(q,params=p)
            rs = RecordSet(initialData=cursor.fetchall(), recordType=cursor.column_names)
        return rs

    def queryOne(self,q,p=[]):
        return query(q,p,connection)[0]

    @dumpCore
    def update(self, table, setDict, keyDict):
        setColumns,setValues = zip(*sorted(setDict.items()))
        keyColumns,keyValues = zip(*sorted(keyDict.items()))
        
        updateQuery = textwrap.dedent("""
            -- Update from Connect class
            update %s
            set %s
            where %s
            """)
        updateQuery %= (table, 
                        ','.join('%s=%%s' % setColumn 
                                 for setColumn 
                                 in setColumns), 
                        '\n\t and '.join('%s=%%s' % keyColumn 
                                         for keyColumn 
                                         in keyColumns))
        
        with self as c:
            cursor = c.connection.cursor()
            cursor.execute(updateQuery,params=setValues+keyValues)

    @dumpCore
    def insert(self, table, columns, values):
        insertQuery = textwrap.dedent("""
            -- Insert from Connect class
            insert into %s
                (%s)
            values
                (%s)
            """)
        insertQuery %= (table, 
                        ','.join(columns), 
                        ','.join(['%s']*len(values)))
        
        with self as c:
            cursor = c.connection.cursor()
            cursor.execute(insertQuery,params=values)
            return cursor.lastrowid



class MetaStORM(type):
    """Metaclass that allows new StORM classes to autoconfigure themselves.
    """
    def __new__(cls, clsname, bases, attributes):        
        return super(MetaStORM,cls).__new__(cls, clsname, bases, attributes)
    
    def __init__(cls, clsname, bases, attributes):
        # Do a null setup for the base class
        if clsname == 'StORM':
            cls._table = ''
        else:
            cls._table = cls._table or clsname
            cls._table = cls._table.lower()
            cls._verify_columns()
        cls._pending = []
        
        for ix,column in enumerate(cls._columns):
            setattr(cls,column,None)
                        
        return super(MetaStORM,cls).__init__(clsname, bases, attributes)
        

    def _verify_columns(cls):
                
        if cls._autoconfigure or not (cls._primary_key_cols and cls._primary_key_auto):
            pkQuery = textwrap.dedent("""
                -- Query for primary keys for StORM
                select c.COLUMN_NAME
                ,	case when c.extra like '%auto_increment%' 
                            then 1
                        else 0
                    end as autoincrements
                from information_schema.columns as c
                where lower(c.table_name) = lower(%s)
                    and c.column_key = 'PRI'
                    and lower(c.table_schema) = lower(%s)
                order by c.ordinal_position
                """)
            pkCols = StORM_Connection().query(pkQuery, [cls._table, cls._schema])
            if pkCols:
                cls._primary_key_cols, cls._primary_key_auto = zip(*(r._tuple for r in pkCols))    
        
        if cls._autoconfigure or not cls._columns:
            columnQuery = textwrap.dedent("""
                -- Query for column names for StORM 
                select c.COLUMN_NAME,
                    case when c.IS_NULLABLE = 'NO' then 0
                        else 1
                    end as IS_NULLABLE
                from information_schema.columns as c
                where c.table_name = %s
                    and c.table_schema = %s
                order by c.ordinal_position
                """)
            columns = StORM_Connection().query(columnQuery, [cls._table, cls._schema])
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
                            

            
class StORM(object):
    """Base class that connects a class to the database.

	When declaring the subclass, set the defaults to persist them.

	NOTE: If no columns are configured, the class will attempt to autoconfigure
	  regardless of whether _autoconfigure is set.
    """
    __metaclass__ = MetaStORM
    
    # set defaults for derived classes here
    _autocommit = False
    _autoconfigure = False
    _table = ''
    _schema = None
    _columns = tuple()
    _primary_key_cols = tuple()
    _primary_key_auto = tuple()
    _non_null_cols = tuple()
    
    _pending = False
    
    def __setattr__(self, attribute, value):
        if attribute in self._columns and getattr(self, attribute) <> value:
            self._pending.append(attribute)
            
        super(StORM,self).__setattr__(attribute, value)
        
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
        
        with StORM_Connection() as c:
            rowID = c.insert(self._table, columns, values)
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
        
        with StORM_Connection() as c:
            c.update(self._table, setValues, keyValues)
            
        self._pending = []

        
    def _commit(self):
        if not self._pending:
            return
        
        # Insert if we don't have the key values yet (at least one of )
        if not all(getattr(self, keyColumn) is not None 
                   for keyColumn 
                   in self._primary_key_cols):
            self._insert()
        else:
            self._update()
        
