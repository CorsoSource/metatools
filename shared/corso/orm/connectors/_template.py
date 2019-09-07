

class _Template_PlasticORM_Connection(object):
    _engine = None
    _param_token = 'PARAM_TOKEN'
    

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
