import common
from autotest_lib.database import db_utils, migrate

TKO_MIGRATION_NAME = '031_rename_tko_tables'
migrations_module = __import__('autotest_lib.tko.migrations', globals(),
                               locals(), [TKO_MIGRATION_NAME])
tko_migration = getattr(migrations_module, TKO_MIGRATION_NAME)

TABLE_NAMES = tko_migration.RENAMES_UP.values()


def migrate_up(manager):
    tko_manager = migrate.get_migration_manager(db_name='TKO', debug=False,
                                                force=False)
    if tko_manager.get_db_version() < 31:
        raise Exception('You must update the TKO database to at least version '
                        '31 before applying AUTOTEST_WEB migration 46')

    if manager.simulate:
        tko_manager.initialize_and_fill_test_db()

    if not manager.force:
        response = raw_input(
                'This migration will merge the autotest_web and tko databases. '
                'Following the migration, the tko database will be dropped. '
                'Any user-added tables in tko will NOT be migrated. This '
                'migration is NOT reversible. Are you sure you want to '
                'continue? (yes/no) ')
        if response != 'yes':
            raise Exception('User has chosen to abort migration')

    db_utils.move_tables(manager, tko_manager, TABLE_NAMES)
    db_utils.drop_database(tko_manager)
    manager.execute_script(tko_migration.RECREATE_VIEWS_UP)


def migrate_down(manager):
    raise Exception('Migration 46 is not reversible!')
