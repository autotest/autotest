import tempfile, shutil, os
from django.core import management
from django.conf import settings
try:
    import autotest.common as common
except ImportError:
    import common

# we need to set DATABASE_ENGINE now, at import time, before the Django database
# system gets initialized.
# django.conf.settings.LazySettings is buggy and requires us to get something
# from it before we set stuff on it.
getattr(settings, 'DATABASES')
settings.DATABASES['default']['ENGINE'] = (
    'autotest_lib.frontend.db.backends.afe_sqlite')
settings.DATABASES['default']['NAME'] = ':memory:'

from django.db import connection
from autotest_lib.frontend.afe import readonly_connection

def run_syncdb(verbosity=0):
    management.call_command('syncdb', verbosity=verbosity, interactive=False)


def destroy_test_database():
    connection.close()
    # Django brilliantly ignores close() requests on in-memory DBs to keep us
    # naive users from accidentally destroying data.  So reach in and close
    # the real connection ourselves.
    # Note this depends on Django internals and will likely need to be changed
    # when we move to Django 1.x.
    real_connection = connection.connection
    if real_connection is not None:
        real_connection.close()
        connection.connection = None


def set_up():
    run_syncdb()
    readonly_connection.ReadOnlyConnection.set_globally_disabled(True)


def tear_down():
    readonly_connection.ReadOnlyConnection.set_globally_disabled(False)
    destroy_test_database()


def print_queries():
    """
    Print all SQL queries executed so far.  Useful for debugging failing tests -
    you can call it from tearDown(), and then execute the single test case of
    interest from the command line.
    """
    for query in connection.queries:
        print query['sql'] + ';\n'
