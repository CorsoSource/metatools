import mysql.connector

import textwrap

from shared.data.recordset import RecordSet
from ..connection import META_QUERIES, PlasticORM_Connection_Base
from ..plastic import PlasticORM_Base


META_QUERIES['mysql'] = {
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


class Mysql_Connector(PlasticORM_Connection_Base):
    _engine = 'mysql'
    _param_token = '%s'
    _keep_alive = True
    connection = None


    def __init__(self, configDict):
        self.config = configDict
        if self._keep_alive:
            self.connect()
        else:
            self.connection = None
    

    def connect(self, forceReconnect=False):
        if self.connection and forceReconnect:
            self.connection.close()
            self.connection = None

        if self.connection is None:
            self.connection = mysql.connector.connect(**self.config)


    def __enter__(self):
        self.connect()
        return self
    

    def __exit__(self, *args):
        if not self.connection == None:
            # Commit changes before closing
            if not self.connection.autocommit:
                self.connection.commit()
            if nost self._keep_alive:
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


class PlasticMysql(PlasticORM_Base):
    _connectionType = Mysql_Connector

    _dbInfo = dict(
        host='mysql8-test.corso.systems',
        port='31825',
        database='test',
        user='root',
        password='********',
        use_pure=True,
        autocommit=True,
        auth_plugin='mysql_native_password',
    )

    pass