
import functools, textwrap

from .connectors._template import _Template_PlasticORM_Connection


META_QUERIES = {}
META_QUERIES[None] = {
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
}


class PlasticORM_Connection_Base(_Template_PlasticORM_Connection):
    """Helper class for connecting to the database.
    Replace and override as needed.
    """            
    _engine = ''
    _param_token = 'PARAM_TOKEN'
    _keep_alive = True
    connection = None


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
