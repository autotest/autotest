import tempfile, shutil, os
from django.core import management
from django.conf import settings
# can't import any django code that depends on the environment setup
import common

def setup_test_environ():
    from autotest_lib.frontend import settings
    management.setup_environ(settings)
    from django.conf import settings
    # django.conf.settings.LazySettings is buggy and requires us to get
    # something from it before we set stuff on it
    getattr(settings, 'DATABASE_ENGINE')
    settings.DATABASE_ENGINE = 'sqlite3'
    settings.DATABASE_NAME = ':memory:'


def set_test_database(database):
    from django.db import connection
    settings.DATABASE_NAME = database
    connection.close()


def backup_test_database():
    temp_fd, backup_path = tempfile.mkstemp(suffix='.test_db_backup')
    os.close(temp_fd)
    shutil.copyfile(settings.DATABASE_NAME, backup_path)
    return backup_path


def restore_test_database(backup_path):
    from django.db import connection
    connection.close()
    shutil.copyfile(backup_path, settings.DATABASE_NAME)


def cleanup_database_backup(backup_path):
    os.remove(backup_path)


def run_syncdb(verbosity=0):
    management.syncdb(verbosity, interactive=False)
