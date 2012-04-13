from django.core import management
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.frontend import settings

management.setup_environ(settings)

def enable_autocommit():
    from django.db import connection
    connection.cursor() # ensure a connection is open
    connection.connection.autocommit(True)
