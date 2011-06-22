from django.db.models.sql import compiler
from autotest_lib.frontend.afe.model_logic import _quote_name

class SQLCompiler(compiler.SQLCompiler):
    def get_from_clause(self):
        from_, params = super(SQLCompiler, self).get_from_clause()

        if hasattr(self.query, "_custom_joins"):
            for join_dict in self.query._custom_joins:
                from_.append('%s %s AS %s ON (%s)'
                             % (join_dict['join_type'],
                                _quote_name(join_dict['table']),
                                _quote_name(join_dict['alias']),
                                join_dict['condition']))
                params.extend(join_dict['condition_values'])

        return from_, params

class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass

class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    pass

class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    pass

class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass

class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
    pass
