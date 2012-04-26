"""
Autotest frontend SQLite based compiler.
"""
from django.db.backends.sqlite3.base import DatabaseOperations as SQLiteDatabaseOperations
from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper


class DatabaseOperations(SQLiteDatabaseOperations):
    compiler_module = "autotest.frontend.db.backends.afe_sqlite.compiler"


class DatabaseWrapper(SQLiteDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.ops = DatabaseOperations()
