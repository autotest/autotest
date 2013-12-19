from django.core import management
from django.conf import settings
try:
    import autotest.common as common
except ImportError:
    import common

#
# This is a database name that will be created and dropped on the go
#
DATABASE_TEST_NAME = 'autotest_web_unittest_run'
settings.DATABASES['default']['NAME'] = DATABASE_TEST_NAME

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
# database, but now the primary testing target is MySQL, which is
# the only currently supported backend.
#
# Now, by default, a test database is created and droped for unittests.
#
COMPLETELY_DESTROY_THE_TEST_DATABASE = True


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
    if COMPLETELY_DESTROY_THE_TEST_DATABASE:
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
    manager.name = DATABASE_TEST_NAME
    manager.create_instance()
    manager.grant_privileges()
    run_syncdb()
    manager.create_views()


def set_up():
    if COMPLETELY_DESTROY_THE_TEST_DATABASE:
        setup_database_via_manager()

    readonly_connection.ReadOnlyConnection.set_globally_disabled(True)


def tear_down():
    readonly_connection.ReadOnlyConnection.set_globally_disabled(False)
    destroy_test_database()
