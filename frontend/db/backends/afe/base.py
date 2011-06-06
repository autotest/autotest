from django.db.backends.mysql.base import DatabaseCreation as MySQLCreation
from django.db.backends.mysql.base import DatabaseOperations as MySQLOperations
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper
from django.db.backends.mysql.base import DatabaseIntrospection as MySQLIntrospection

try:
    import MySQLdb as Database
except ImportError, e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading MySQLdb module: %s" % e)


class DatabaseOperations(MySQLOperations):
    compiler_module = "autotest_lib.frontend.db.backends.afe.compiler"


class DatabaseWrapper(MySQLDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.creation = MySQLCreation(self)
        self.ops = DatabaseOperations()
        self.introspection = MySQLIntrospection(self)
