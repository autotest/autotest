#!/usr/bin/python2.4
#
# Copyright 2008 Google Inc. All Rights Reserved.
"""
This utility allows for easy updating, removing and importing
of tests into the autotest_web autotests table.

Example of updating client side tests:
./tests.py -t /usr/local/autotest/client/tests 

If for example not all of your control files adhere to the standard outlined at
http://test.kernel.org/autotest/ControlRequirements

You can force options:
./tests.py --test-type server -t /usr/local/autotest/server/tests


Most options should be fairly self explanatory use --help to display them.
"""


import time, re, os, MySQLdb, sys, optparse
import common
from autotest_lib.client.common_lib import control_data, test, global_config
from autotest_lib.client.common_lib import utils

# Defaults
AUTHOR = 'Autotest Team'
DEPENDENCIES = ()
DOC = 'unknown'
EXPERIMENTAL = 0
RUN_VERIFY = 1
SYNC_COUNT = 1
TEST_TYPE = 1
TEST_TIME = 1
TEST_CLASS = 'Canned Test Sets'
TEST_CATEGORY = 'Functional'

# Global
DRY_RUN = False


def main(argv):
    """Main function"""
    global DRY_RUN
    parser = optparse.OptionParser()
    parser.add_option('-c', '--db-clear-tests',
                      dest='clear_tests', action='store_true',
                      default=False,
                help='Clear client and server tests with invalid control files')
    parser.add_option('-d', '--dry-run',
                      dest='dry_run', action='store_true', default=False,
                      help='Dry run for operation')
    parser.add_option('-A', '--add-experimental',
                      dest='add_experimental', action='store_true',
                      default=False,
                      help='Add experimental tests to frontend')
    parser.add_option('-N', '--add-noncompliant',
                      dest='add_noncompliant', action='store_true',
                      default=False,
                      help='Skip any tests that are not compliant')
    parser.add_option('-t', '--tests-dir', dest='tests_dir',
                      help='Directory to recursively check for control.*')
    parser.add_option('-p', '--test-type', dest='test_type', default=TEST_TYPE,
                      help='Default test type for tests (Client=1, Server=2)')
    parser.add_option('-a', '--test-author', dest='author', default=AUTHOR,
                      help='Set a default author for tests')
    parser.add_option('-n', '--test-dependencies', dest='dependencies',
                      default=DEPENDENCIES,
                      help='Set default dependencies for tests')
    parser.add_option('-v', '--test-run-verify', dest='run_verify',
                      default=RUN_VERIFY,
                      help='Set default run_verify (0, 1)')
    parser.add_option('-e', '--test-experimental', dest='experimental',
                      default=EXPERIMENTAL,
                      help='Set default experimental (0, 1)')
    parser.add_option('-y', '--test-sync-count', dest='sync_count',
                      default=SYNC_COUNT,
                      help='Set a default sync_count (1, >1)')
    parser.add_option('-m', '--test-time', dest='test_time', default=TEST_TIME,
                      help='Set a default time for tests')
    parser.add_option('-g', '--test-category', dest='test_category',
                      default=TEST_CATEGORY,
                      help='Set a default time for tests')
    parser.add_option('-l', '--test-class', dest='test_class',
                      default=TEST_CLASS, help='Set a default test class')
    parser.add_option('-r', '--control-pattern', dest='control_pattern',
                      default='^control.*',
               help='The pattern to look for in directories for control files')
    parser.add_option('-z', '--autotest_dir', dest='autotest_dir',
                      default='/usr/local/autotest',
                      help='Autotest directory root')
    options, args = parser.parse_args()
    DRY_RUN = options.dry_run
    if len(argv) < 2:
        parser.print_help()
        return 1

    if options.clear_tests:
        tests = get_tests_from_db(autotest_dir=options.autotest_dir)
        test_paths = [tests['missing'][t] for t in tests['missing']]
        db_remove_tests(test_paths)
    if options.tests_dir:
        tests = get_tests_from_fs(options.tests_dir, options.control_pattern,
                                  add_noncompliant=options.add_noncompliant)
        update_tests_in_db(tests, author=options.author,
                           dependencies=options.dependencies,
                           experimental=options.experimental,
                           run_verify=options.run_verify,
                           doc=DOC,
                           sync_count=options.sync_count,
                           test_type=options.test_type,
                           test_time=options.test_time,
                           test_class=options.test_class,
                           test_category=options.test_category,
                           add_experimental=options.add_experimental,
                           add_noncompliant=options.add_noncompliant,
                           autotest_dir=options.autotest_dir)


def db_remove_tests(tests):
    """Remove tests from autotest_web that do not have valid control files

       Arguments:
        tests: a list of control file relative paths used as keys for deletion.
    """
    connection=db_connect()
    cursor = connection.cursor()
    for test in tests:
        print "Removing " + test
        sql = "DELETE FROM autotests WHERE path='%s'" % test
        db_execute(cursor, sql)

    connection.commit()
    connection.close()


def update_tests_in_db(tests, dry_run=False, add_experimental=False,
                       autotest_dir="/usr/local/autotest/", **dargs):
    """Update or add each test to the database"""
    connection=db_connect()
    cursor = connection.cursor()
    for test in tests:
        new_test = dargs.copy()
        new_test['path'] = test.replace(autotest_dir, '').lstrip('/')
        # Create a name for the test
        for key in dir(tests[test]):
            if not key.startswith('__'):
                value = getattr(tests[test], key)
                if not callable(value):
                    new_test[key] = value
        # This only takes place if --add-noncompliant is provided on the CLI
        if 'name' not in new_test:
            test_new_test = test.split('/')
            if test_new_test[-1] == 'control':
                new_test['name'] = test_new_test[-2]
            else:
                control_name = "%s:%s"
                control_name %= (test_new_test[-2],
                                 test_new_test[-1]) 
                new_test['name'] = control_name.replace('control.', '')
        # Experimental Check
        if not add_experimental:
            if int(new_test['experimental']):
                continue
        # clean tests for insertion into db
        new_test = dict_db_clean(new_test)
        sql = "SELECT name,path FROM autotests WHERE path='%s' LIMIT 1"
        sql %= new_test['path']
        cursor.execute(sql)
        # check for entries already in existence
        results = cursor.fetchall()
        if results:
            sql = "UPDATE autotests SET name='%s', test_class='%s',"\
                  "description='%s', test_type=%d, path='%s',"\
                  "synch_type=%d, author='%s', dependencies='%s',"\
                  "experimental=%d, run_verify=%d, test_time=%d,"\
                  "test_category='%s', sync_count=%d"\
                  " WHERE path='%s'"
            sql %= (new_test['name'], new_test['test_class'], new_test['doc'],
                    int(new_test['test_type']), new_test['path'],
                    int(new_test['synch_type']), new_test['author'],
                    new_test['dependencies'], int(new_test['experimental']),
                    int(new_test['run_verify']), new_test['test_time'],
                    new_test['test_category'], new_test['sync_count'], new_test['path'])
        else:
            # Create a relative path
            path = test.replace(autotest_dir, '')
            sql = "INSERT INTO autotests"\
                  "(name, test_class, description, test_type, path, "\
                  "synch_type, author, dependencies, experimental, "\
                  "run_verify, test_time, test_category, sync_count) "\
                  "VALUES('%s','%s','%s',%d,'%s',%d,'%s','%s',%d,%d,%d,"\
                  "'%s',%d)"
            sql %= (new_test['name'], new_test['test_class'], new_test['doc'],
                    int(new_test['test_type']), new_test['path'],
                    int(new_test['synch_type']), new_test['author'],
                    new_test['dependencies'], int(new_test['experimental']),
                    int(new_test['run_verify']), new_test['test_time'],
                    new_test['test_category'], new_test['sync_count'])

        db_execute(cursor, sql)

    connection.commit()
    connection.close()


def dict_db_clean(test):
    """Take a tests dictionary from update_db and make it pretty for SQL"""

    test_type = { 'client' : 1,
                  'server' : 2, }
    test_time = { 'short' : 1,
                  'medium' : 2,
                  'long' : 3, }

    test['name'] = MySQLdb.escape_string(test['name'])
    test['author'] = MySQLdb.escape_string(test['author'])
    test['test_class'] = MySQLdb.escape_string(test['test_class'])
    test['test_category'] = MySQLdb.escape_string(test['test_category'])
    test['doc'] = MySQLdb.escape_string(test['doc'])
    test['dependencies'] = ", ".join(test['dependencies'])
    # TODO Fix when we move from synch_type to sync_count
    if test['sync_count'] == 1:
        test['synch_type'] = 1
    else:
        test['synch_type'] = 2
    try:
        test['test_type'] = int(test['test_type'])
        if test['test_type'] != 1 and test['test_type'] != 2:
            raise Exception('Incorrect number %d for test_type' %
                            test['test_type'])
    except ValueError:
        pass
    try:
        test['test_time'] = int(test['test_time'])
        if test['test_time'] < 1 or test['test_time'] > 3:
            raise Exception('Incorrect number %d for test_time' %
                            test['test_time'])
    except ValueError:
        pass

    if str == type(test['test_time']):
        test['test_time'] = test_time[test['test_time'].lower()]
    if str == type(test['test_type']):
        test['test_type'] = test_type[test['test_type'].lower()]
    return test


def get_tests_from_db(autotest_dir='/usr/local/autotest'):
    """Get the tests from the DB.
     Returns:
        dictionary of form: 
            data['valid'][test_name] = parsed object
            data['missing'][test_name] = relative_path to test
    """
    connection = db_connect()
    cursor = connection.cursor()
    tests = {}
    tests['valid'] = {}
    tests['missing'] = {}
    cursor.execute("SELECT name,path from autotests")
    results = cursor.fetchall()
    for row in results:
        name = row[0]
        relative_path = row[1]
        control_path = os.path.join(autotest_dir, relative_path)
        if os.path.exists(control_path):
            tests['valid'][name] = control_data.parse_control(control_path)
        else:
            # test doesn't exist
            tests['missing'][name] = relative_path
    connection.close()
    return tests


def get_tests_from_fs(parent_dir, control_pattern, add_noncompliant=False):
    """Find control jobs in location and create one big job
       Returns:
        dictionary of the form:
            tests[file_path] = parsed_object

    """
    tests = {}
    for dir in [ parent_dir ]:
        files = recursive_walk(dir, control_pattern)
        for file in files:
            if not add_noncompliant:
                try:
                    found_test = control_data.parse_control(file,
                                                            raise_warnings=True)
                    tests[file] = found_test
                except control_data.ControlVariableException, e:
                    print "Skipping %s\n%s" % (file, e)
                    pass
            else:
                found_test = control_data.parse_control(file)
                tests[file] = found_test
    return tests


def recursive_walk(path, wildcard):
    """Recurisvely go through a directory.
        Returns:
        A list of files that match wildcard
    """
    files = []
    directories = [ path ]
    while len(directories)>0:
        directory = directories.pop()
        for name in os.listdir(directory):
            fullpath = os.path.join(directory, name)
            if os.path.isfile(fullpath):
                # if we are a control file
                if re.search(wildcard, name):
                    files.append(fullpath)
            elif os.path.isdir(fullpath):
                directories.append(fullpath)
    return files


def db_connect():
    """Connect to the AUTOTEST_WEB database and return a connect object."""
    c = global_config.global_config
    db_host = c.get_config_value('AUTOTEST_WEB', 'host')
    db_name = c.get_config_value('AUTOTEST_WEB', 'database')
    username = c.get_config_value('AUTOTEST_WEB', 'user')
    password = c.get_config_value('AUTOTEST_WEB', 'password')
    connection = MySQLdb.connect(host=db_host, db=db_name,
                                 user=username,
                                 passwd=password)
    return connection


def db_execute(cursor, sql):
    """Execute SQL or print out what would be executed if dry_run is defined"""

    if DRY_RUN:
        print "Would run: " + sql
    else:
        cursor.execute(sql)


if __name__ == "__main__":
    main(sys.argv)
