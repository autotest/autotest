from django.core import management
import common
from autotest_lib.frontend import settings
from autotest_lib.database import db_utils

AFE_MIGRATION_NAME = '059_drone_sets_permissions'
migrations_module = __import__('autotest_lib.frontend.migrations', globals(),
                               locals(), [AFE_MIGRATION_NAME])
migration_059 = getattr(migrations_module, AFE_MIGRATION_NAME)


def migrate_up(manager):
    """
    If the auth tables don't exist, we shouldn't try to set the permissions.

    See migration 059
    """
    if db_utils.auth_tables_exist(manager):
        management.setup_environ(settings)
        # These have to be imported after the environment is set up
        from django.contrib.contenttypes import management as content_management
        from django.contrib.auth import management as auth_management
        from django.db import models as db_models

        content_management.update_all_contenttypes()
        for app in db_models.get_apps():
            auth_management.create_permissions(app, None, 2)

        manager.execute_script(migration_059.UP_SQL)


def migrate_down(manager):
    if db_utils.auth_tables_exist(manager):
        manager.execute_script(migration_059.DOWN_SQL)
