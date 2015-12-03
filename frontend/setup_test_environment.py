from django.conf import settings
from django.core import management

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

# we need to set DATABASE_ENGINE now, at import time, before the Django database
# system gets initialized.
# django.conf.settings.LazySettings is buggy and requires us to get something
# from it before we set stuff on it.
getattr(settings, 'DATABASES')
settings.DATABASES['default']['ENGINE'] = (
    'autotest.frontend.db.backends.afe_sqlite')
settings.DATABASES['default']['NAME'] = ':memory:'


#
# Enabling the DEBUG setting is the most straightforward way to prevent Django
# from enforcing conditions that should be enforced during production, but not
# necessarily under a test environment (such as when running unittests. One
# example is the HOSTS_ALLOWED check that was introduced in Django 1.5.
#
settings.DEBUG = True


# We have to update the south backend since the engine also gets changed here
south_backend = settings.SOUTH_BACKENDS[settings.AUTOTEST_DEFAULT['ENGINE']]
settings.SOUTH_DATABASE_ADAPTERS['default'] = south_backend

from django.db import connection
from autotest.frontend.afe import readonly_connection
from autotest.installation_support import database_manager

# PLEASE READ:
#
# Previously the unittests would run only on the memory based SQLite
# database, but now that it can also run on other backends such as MySQL
# there's no easy way to make the test environment decide which one to
# use.
#
# Now *developers* can change the settings.DATABASES configurations (or
# comment them out to use the configuration on global_config.ini) to run
# the unittests on other backends.
#
# WARNING: if you change the following variable, and have a database
# with data, you WILL LOSE IT. Only set the following variable to true and
# run the unittests on a development system and database.
COMPLETELY_DESTROY_THE_DATABASE = False


def run_syncdb(verbosity=0):
    management.call_command('syncdb', verbosity=verbosity, interactive=False)
    management.call_command('migrate', 'afe', verbosity=verbosity,
                            interactive=False)
    management.call_command('migrate', 'tko', verbosity=verbosity,
                            interactive=False)


def destroy_test_database():
    connection.close()
    # Django brilliantly ignores close() requests on in-memory DBs to keep us
    # naive users from accidentally destroying data.  So reach in and close
    # the real connection ourselves.
    # Note this depends on Django internals and will likely need to be changed
    # when we move to Django 1.x.
    if ((not settings.DATABASES['default']['ENGINE'].endswith('sqlite')) and
            COMPLETELY_DESTROY_THE_DATABASE):
        database_name = settings.DATABASES['default']['NAME']
        cur = connection.cursor()
        cur.execute('DROP DATABASE IF EXISTS %s' % database_name)

    real_connection = connection.connection
    if real_connection is not None:
        real_connection.close()
        connection.connection = None


def setup_database_via_manager():
    '''
    Creates a database manager instance
    '''
    engine = settings.DATABASES['default']['ENGINE']
    rdbms_type = database_manager.engine_to_rdbms_type(engine)
    manager = database_manager.get_manager_from_config(rdbms_type=rdbms_type)
    manager.create_instance()
    manager.grant_privileges()


def set_up():
    if COMPLETELY_DESTROY_THE_DATABASE:
        setup_database_via_manager()

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
