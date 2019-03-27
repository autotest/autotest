from django.db.backends.mysql.base import DatabaseCreation as MySQLCreation
from django.db.backends.mysql.base import DatabaseIntrospection as MySQLIntrospection
from django.db.backends.mysql.base import DatabaseOperations as MySQLOperations
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

try:
    import MySQLdb as Database
except ImportError as e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Error loading MySQLdb module: %s" % e)


class DatabaseOperations(MySQLOperations):
    compiler_module = "autotest.frontend.db.backends.afe.compiler"


class DatabaseWrapper(MySQLDatabaseWrapper):

    def __init__(self, *args, **kwargs):
        self.connection = None
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.creation = MySQLCreation(self)
        try:
            self.ops = DatabaseOperations()
        except TypeError:
            self.ops = DatabaseOperations(connection=kwargs.get('connection'))
        self.introspection = MySQLIntrospection(self)

    def _valid_connection(self):
        if self.connection is not None:
            if self.connection.open:
                try:
                    self.connection.ping()
                    return True
                except Database.DatabaseError:
                    self.connection.close()
                    self.connection = None
        return False
