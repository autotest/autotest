#!/usr/bin/python -u

import os
import sys
import re
import tempfile
import optparse

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import utils
from autotest.database_legacy import database_connection

MIGRATE_TABLE = 'migrate_info'

_AUTODIR = os.path.join(os.path.dirname(__file__), '..')
_MIGRATIONS_DIRS = os.path.join(_AUTODIR, 'database_legacy', 'migrations')


class Migration(object):
    _UP_ATTRIBUTES = ('migrate_up', 'UP_SQL')
    _DOWN_ATTRIBUTES = ('migrate_down', 'DOWN_SQL')

    def __init__(self, name, version, module):
        self.name = name
        self.version = version
        self.module = module
        self._check_attributes(self._UP_ATTRIBUTES)
        self._check_attributes(self._DOWN_ATTRIBUTES)

    @classmethod
    def from_file(cls, filename):
        version = int(filename[:3])
        name = filename[:-3]
        module = __import__(name, globals(), locals(), [])
        return cls(name, version, module)

    def _check_attributes(self, attributes):
        method_name, sql_name = attributes
        assert (hasattr(self.module, method_name) or
                hasattr(self.module, sql_name))

    def _execute_migration(self, attributes, manager):
        method_name, sql_name = attributes
        method = getattr(self.module, method_name, None)
        if method:
            assert callable(method)
            method(manager)
        else:
            sql = getattr(self.module, sql_name)
            assert isinstance(sql, basestring)
            manager.execute_script(sql)

    def migrate_up(self, manager):
        self._execute_migration(self._UP_ATTRIBUTES, manager)

    def migrate_down(self, manager):
        self._execute_migration(self._DOWN_ATTRIBUTES, manager)


class MigrationManager(object):
    connection = None
    cursor = None
    migrations_dir = None

    def __init__(self, database_connection, migrations_dir=None, force=False):
        self._database = database_connection
        self.force = force
        # A boolean, this will only be set to True if this migration should be
        # simulated rather than actually taken. For use with migrations that
        # may make destructive queries
        self.simulate = False
        self._set_migrations_dir(migrations_dir)

    def _set_migrations_dir(self, migrations_dir=None):
        config_section = self._config_section()
        if migrations_dir is None:
            migrations_dir = os.path.abspath(_MIGRATIONS_DIRS)
        self.migrations_dir = migrations_dir
        sys.path.append(migrations_dir)
        assert os.path.exists(migrations_dir), migrations_dir + " doesn't exist"

    def _config_section(self):
        return self._database.settings_section

    def get_db_name(self):
        return self._database.get_database_info()['db_name']

    def execute(self, query, *parameters):
        return self._database.execute(query, parameters)

    def execute_script(self, script):
        sql_statements = [statement.strip()
                          for statement in script.split(';')
                          if statement.strip()]
        for statement in sql_statements:
            self.execute(statement)

    def check_migrate_table_exists(self):
        try:
            self.execute("SELECT * FROM %s" % MIGRATE_TABLE)
            return True
        except self._database.DatabaseError:
            # we can't check for more specifics due to differences between DB
            # backends (we can't even check for a subclass of DatabaseError)
            return False

    def create_migrate_table(self):
        if not self.check_migrate_table_exists():
            self.execute("CREATE TABLE %s (`version` integer)" %
                         MIGRATE_TABLE)
        else:
            self.execute("DELETE FROM %s" % MIGRATE_TABLE)
        self.execute("INSERT INTO %s VALUES (0)" % MIGRATE_TABLE)
        assert self._database.rowcount == 1

    def set_db_version(self, version):
        assert isinstance(version, int)
        self.execute("UPDATE %s SET version=%%s" % MIGRATE_TABLE,
                     version)
        assert self._database.rowcount == 1

    def get_db_version(self):
        if not self.check_migrate_table_exists():
            return 0
        rows = self.execute("SELECT * FROM %s" % MIGRATE_TABLE)
        if len(rows) == 0:
            return 0
        assert len(rows) == 1 and len(rows[0]) == 1
        return rows[0][0]

    def get_migrations(self, minimum_version=None, maximum_version=None):
        migrate_files = [filename for filename
                         in os.listdir(self.migrations_dir)
                         if re.match(r'^\d\d\d_.*\.py$', filename)]
        migrate_files.sort()
        migrations = [Migration.from_file(filename)
                      for filename in migrate_files]
        if minimum_version is not None:
            migrations = [migration for migration in migrations
                          if migration.version >= minimum_version]
        if maximum_version is not None:
            migrations = [migration for migration in migrations
                          if migration.version <= maximum_version]
        return migrations

    def do_migration(self, migration, migrate_up=True):
        print 'Applying migration %s' % migration.name,  # no newline
        if migrate_up:
            print 'up'
            assert self.get_db_version() == migration.version - 1
            migration.migrate_up(self)
            new_version = migration.version
        else:
            print 'down'
            assert self.get_db_version() == migration.version
            migration.migrate_down(self)
            new_version = migration.version - 1
        self.set_db_version(new_version)

    def migrate_to_version(self, version):
        current_version = self.get_db_version()
        if current_version == 0 and self._config_section() == 'AUTOTEST_WEB':
            self._migrate_from_base()
            current_version = self.get_db_version()

        if current_version < version:
            lower, upper = current_version, version
            migrate_up = True
        else:
            lower, upper = version, current_version
            migrate_up = False

        migrations = self.get_migrations(lower + 1, upper)
        if not migrate_up:
            migrations.reverse()
        for migration in migrations:
            self.do_migration(migration, migrate_up)

        assert self.get_db_version() == version
        print 'At version', version

    def _migrate_from_base(self):
        self.confirm_initialization()

        migration_script = utils.read_file(
            os.path.join(os.path.dirname(__file__), 'schema_068.sql'))
        migration_script = migration_script % (
            dict(username=self._database.get_database_info()['username']))
        self.execute_script(migration_script)

    def confirm_initialization(self):
        if not self.force:
            response = raw_input(
                'Your %s database does not appear to be initialized.  Do you '
                'want to recreate it (this will result in loss of any existing '
                'data) (yes/No)? ' % self.get_db_name())
            if response != 'yes':
                raise Exception('User has chosen to abort migration')

    def get_latest_version(self):
        migrations = self.get_migrations()
        return migrations[-1].version

    def migrate_to_latest(self):
        latest_version = self.get_latest_version()
        self.migrate_to_version(latest_version)

    def initialize_test_db(self):
        db_name = self.get_db_name()
        test_db_name = 'test_' + db_name
        # first, connect to no DB so we can create a test DB
        self._database.connect(db_name='')
        print 'Creating test DB', test_db_name
        self.execute('CREATE DATABASE ' + test_db_name)
        self._database.disconnect()
        # now connect to the test DB
        self._database.connect(db_name=test_db_name)

    def remove_test_db(self):
        print 'Removing test DB'
        self.execute('DROP DATABASE ' + self.get_db_name())
        # reset connection back to real DB
        self._database.disconnect()
        self._database.connect()

    def get_mysql_args(self):
        return ('-u %(username)s -p%(password)s -h %(host)s %(db_name)s' %
                self._database.get_database_info())

    def migrate_to_version_or_latest(self, version):
        if version is None:
            self.migrate_to_latest()
        else:
            self.migrate_to_version(version)

    def do_sync_db(self, version=None):
        print 'Migration starting for database', self.get_db_name()
        self.migrate_to_version_or_latest(version)
        print 'Migration complete'

    def test_sync_db(self, version=None):
        """
        Create a fresh DB and run all migrations on it.
        """
        self.initialize_test_db()
        try:
            print 'Starting migration test on DB', self.get_db_name()
            self.migrate_to_version_or_latest(version)
            # show schema to the user
            os.system('mysqldump %s --no-data=true '
                      '--add-drop-table=false' %
                      self.get_mysql_args())
        finally:
            self.remove_test_db()
        print 'Test finished successfully'

    def simulate_sync_db(self, version=None):
        """
        Create a fresh DB, copy the existing DB to it, and then
        try to synchronize it.
        """
        db_version = self.get_db_version()
        # don't do anything if we're already at the latest version
        if db_version == self.get_latest_version():
            print 'Skipping simulation, already at latest version'
            return
        # get existing data
        self.initialize_and_fill_test_db()
        try:
            print 'Starting migration test on DB', self.get_db_name()
            self.migrate_to_version_or_latest(version)
        finally:
            self.remove_test_db()
        print 'Test finished successfully'

    def initialize_and_fill_test_db(self):
        print 'Dumping existing data'
        dump_fd, dump_file = tempfile.mkstemp('.migrate_dump')
        os.system('mysqldump %s >%s' %
                  (self.get_mysql_args(), dump_file))
        # fill in test DB
        self.initialize_test_db()
        print 'Filling in test DB'
        os.system('mysql %s <%s' % (self.get_mysql_args(), dump_file))
        os.close(dump_fd)
        os.remove(dump_file)


class OptionParser(optparse.OptionParser):

    ACTIONS = ['sync', 'test', 'simulate', 'safesync']

    def __init__(self):
        actions_info = '  <action>\t\tOne of: %s\n' % ', '.join(self.ACTIONS)
        usage_info = 'Usage: %prog [options] <action>'

        if sys.version_info[0:2] < (2, 6):
            optparse.OptionParser.__init__(self, usage=usage_info,
                                           description=actions_info)
        else:
            optparse.OptionParser.__init__(self, usage=usage_info,
                                           epilog=actions_info)

        self.add_option("-d", "--database", default="AUTOTEST_WEB",
                        help="which database to act on (defaults to %default)")

        self.add_option("-f", "--force", action="store_true",
                        help="don't ask for confirmation")

        self.add_option('--debug', action='store_true',
                        help='print all DB queries')


def get_migration_manager(db_name, debug, force):
    database = database_connection.DatabaseConnection(db_name)
    database.debug = debug
    database.reconnect_enabled = False
    database.connect()
    return MigrationManager(database, force=force)


def main():
    parser = OptionParser()
    (options, args) = parser.parse_args()
    manager = get_migration_manager(db_name=options.database,
                                    debug=options.debug, force=options.force)

    if len(args) > 0:
        if len(args) > 1:
            version = int(args[1])
        else:
            version = None
        if args[0] == 'sync':
            manager.do_sync_db(version)
        elif args[0] == 'test':
            manager.simulate = True
            manager.test_sync_db(version)
        elif args[0] == 'simulate':
            manager.simulate = True
            manager.simulate_sync_db(version)
        elif args[0] == 'safesync':
            print 'Simulating migration'
            manager.simulate = True
            manager.simulate_sync_db(version)
            print 'Performing real migration'
            manager.simulate = False
            manager.do_sync_db(version)
        else:
            parser.print_help()
        return

    parser.print_help()


if __name__ == '__main__':
    main()
