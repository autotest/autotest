#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.
"""
This utility allows for easy updating, removing and importing
of tests into the autotest_web autotests table.

Example of updating client side tests:
./test_importer.py -t /usr/local/autotest/client/tests

If, for example, not all of your control files adhere to the standard outlined
at http://autotest.kernel.org/wiki/ControlRequirements, you can force options:

./test_importer.py --test-type server -t /usr/local/autotest/server/tests

You would need to pass --add-noncompliant to include such control files,
however.  An easy way to check for compliance is to run in dry mode:

./test_importer.py --dry-run -t /usr/local/autotest/server/tests/mytest

Or to check a single control file, you can use check_control_file_vars.py.

Running with no options is equivalent to --add-all --db-clear-tests.

Most options should be fairly self explanatory, use --help to display them.
"""


import logging, time, re, os, MySQLdb, sys, optparse, compiler
import common
from autotest_lib.client.common_lib import control_data, test, global_config
from autotest_lib.client.common_lib import utils


logging.basicConfig(level=logging.DEBUG)
# Global
DRY_RUN = False
DEPENDENCIES_NOT_FOUND = set()

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
    parser.add_option('-A', '--add-all',
                      dest='add_all', action='store_true',
                      default=False,
                      help='Add site_tests, tests, and test_suites')
    parser.add_option('-S', '--add-samples',
                      dest='add_samples', action='store_true',
                      default=False,
                      help='Add samples.')
    parser.add_option('-E', '--add-experimental',
                      dest='add_experimental', action='store_true',
                      default=True,
                      help='Add experimental tests to frontend')
    parser.add_option('-N', '--add-noncompliant',
                      dest='add_noncompliant', action='store_true',
                      default=False,
                      help='Add non-compliant tests (i.e. tests that do not '
                           'define all required control variables)')
    parser.add_option('-p', '--profile-dir', dest='profile_dir',
                      help='Directory to recursively check for profiles')
    parser.add_option('-t', '--tests-dir', dest='tests_dir',
                      help='Directory to recursively check for control.*')
    parser.add_option('-r', '--control-pattern', dest='control_pattern',
                      default='^control.*',
               help='The pattern to look for in directories for control files')
    parser.add_option('-v', '--verbose',
                      dest='verbose', action='store_true', default=False,
                      help='Run in verbose mode')
    parser.add_option('-z', '--autotest_dir', dest='autotest_dir',
                      default=os.path.join(os.path.dirname(__file__), '..'),
                      help='Autotest directory root')
    options, args = parser.parse_args()
    DRY_RUN = options.dry_run
    # Make sure autotest_dir is the absolute path
    options.autotest_dir = os.path.abspath(options.autotest_dir)

    if len(args) > 0:
        print "Invalid option(s) provided: ", args
        parser.print_help()
        return 1

    if len(argv) == 1:
        update_all(options.autotest_dir, options.add_noncompliant,
                   options.add_experimental, options.verbose)
        db_clean_broken(options.autotest_dir, options.verbose)
        return 0

    if options.add_all:
        update_all(options.autotest_dir, options.add_noncompliant,
                   options.add_experimental, options.verbose)
    if options.add_samples:
        update_samples(options.autotest_dir, options.add_noncompliant,
                       options.add_experimental, options.verbose)
    if options.clear_tests:
        db_clean_broken(options.autotest_dir, options.verbose)
    if options.tests_dir:
        options.tests_dir = os.path.abspath(options.tests_dir)
        tests = get_tests_from_fs(options.tests_dir, options.control_pattern,
                                  add_noncompliant=options.add_noncompliant)
        update_tests_in_db(tests, add_experimental=options.add_experimental,
                           add_noncompliant=options.add_noncompliant,
                           autotest_dir=options.autotest_dir,
                           verbose=options.verbose)
    if options.profile_dir:
        profilers = get_tests_from_fs(options.profile_dir, '.*py$')
        update_profilers_in_db(profilers, verbose=options.verbose,
                               add_noncompliant=options.add_noncompliant,
                               description='NA')


def update_all(autotest_dir, add_noncompliant, add_experimental, verbose):
    """Function to scan through all tests and add them to the database."""
    for path in [ 'server/tests', 'server/site_tests', 'client/tests',
                  'client/site_tests']:
        test_path = os.path.join(autotest_dir, path)
        if not os.path.exists(test_path):
            continue
        if verbose:
            print "Scanning " + test_path
        tests = []
        tests = get_tests_from_fs(test_path, "^control.*",
                                 add_noncompliant=add_noncompliant)
        update_tests_in_db(tests, add_experimental=add_experimental,
                           add_noncompliant=add_noncompliant,
                           autotest_dir=autotest_dir,
                           verbose=verbose)
    test_suite_path = os.path.join(autotest_dir, 'test_suites')
    if os.path.exists(test_suite_path):
        if verbose:
            print "Scanning " + test_suite_path
        tests = get_tests_from_fs(test_suite_path, '.*',
                                 add_noncompliant=add_noncompliant)
        update_tests_in_db(tests, add_experimental=add_experimental,
                           add_noncompliant=add_noncompliant,
                           autotest_dir=autotest_dir,
                           verbose=verbose)

    profilers_path = os.path.join(autotest_dir, "client/profilers")
    if os.path.exists(profilers_path):
        if verbose:
            print "Scanning " + profilers_path
        profilers = get_tests_from_fs(profilers_path, '.*py$')
        update_profilers_in_db(profilers, verbose=verbose,
                               add_noncompliant=add_noncompliant,
                               description='NA')
    # Clean bad db entries
    db_clean_broken(autotest_dir, verbose)


def update_samples(autotest_dir, add_noncompliant, add_experimental, verbose):
    sample_path = os.path.join(autotest_dir, 'server/samples')
    if os.path.exists(sample_path):
        if verbose:
            print "Scanning " + sample_path
        tests = get_tests_from_fs(sample_path, '.*srv$',
                                  add_noncompliant=add_noncompliant)
        update_tests_in_db(tests, add_experimental=add_experimental,
                           add_noncompliant=add_noncompliant,
                           autotest_dir=autotest_dir,
                           verbose=verbose)


def db_clean_broken(autotest_dir, verbose):
    """Remove tests from autotest_web that do not have valid control files

       Arguments:
        tests: a list of control file relative paths used as keys for deletion.
    """
    connection=db_connect()
    cursor = connection.cursor()
    # Get tests
    sql = "SELECT id, path FROM autotests";
    cursor.execute(sql)
    results = cursor.fetchall()
    for test_id, path in results:
        full_path = os.path.join(autotest_dir, path)
        if not os.path.isfile(full_path):
            if verbose:
                print "Removing " + path
            db_execute(cursor, "DELETE FROM autotests WHERE id=%s" % test_id)
            db_execute(cursor, "DELETE FROM autotests_dependency_labels WHERE "
                               "test_id=%s" % test_id)

    # Find profilers that are no longer present
    profilers = []
    sql = "SELECT name FROM profilers"
    cursor.execute(sql)
    results = cursor.fetchall()
    for path in results:
        full_path = os.path.join(autotest_dir, "client/profilers", path[0])
        if not os.path.exists(full_path):
            if verbose:
                print "Removing " + path[0]
            sql = "DELETE FROM profilers WHERE name='%s'" % path[0]
            db_execute(cursor, sql)


    connection.commit()
    connection.close()


def update_profilers_in_db(profilers, verbose=False, description='NA',
                           add_noncompliant=False):
    """Update profilers in autotest_web database"""
    connection=db_connect()
    cursor = connection.cursor()
    for profiler in profilers:
        name = os.path.basename(profiler).rstrip(".py")
        if not profilers[profiler]:
            if add_noncompliant:
                doc = description
            else:
                print "Skipping %s, missing docstring" % profiler
        else:
            doc = profilers[profiler]
        # check if test exists
        sql = "SELECT name FROM profilers WHERE name='%s'" % name
        cursor.execute(sql)
        results = cursor.fetchall()
        if results:
            sql = "UPDATE profilers SET name='%s', description='%s' "\
                  "WHERE name='%s'"
            sql %= (MySQLdb.escape_string(name), MySQLdb.escape_string(doc),
                    MySQLdb.escape_string(name))
        else:
            # Insert newly into DB
            sql = "INSERT into profilers (name, description) VALUES('%s', '%s')"
            sql %= (MySQLdb.escape_string(name), MySQLdb.escape_string(doc))

        db_execute(cursor, sql)

    connection.commit()
    connection.close()


def update_tests_in_db(tests, dry_run=False, add_experimental=False,
                       add_noncompliant=False, verbose=False,
                       autotest_dir=None):
    """Update or add each test to the database"""
    connection=db_connect()
    cursor = connection.cursor()
    new_test_dicts = []
    for test in tests:
        new_test = {}
        new_test['path'] = test.replace(autotest_dir, '').lstrip('/')
        if verbose:
            print "Processing " + new_test['path']
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
        new_test_dicts.append(new_test)
        sql = "SELECT name,path FROM autotests WHERE path='%s' LIMIT 1"
        sql %= new_test['path']
        cursor.execute(sql)
        # check for entries already in existence
        results = cursor.fetchall()
        if results:
            sql = ("UPDATE autotests SET name='%s', test_class='%s',"
                  "description='%s', test_type=%d, path='%s',"
                  "author='%s', dependencies='%s',"
                  "experimental=%d, run_verify=%d, test_time=%d,"
                  "test_category='%s', sync_count=%d"
                  " WHERE path='%s'")
            sql %= (new_test['name'], new_test['test_class'], new_test['doc'],
                    int(new_test['test_type']), new_test['path'],
                    new_test['author'],
                    new_test['dependencies'], int(new_test['experimental']),
                    int(new_test['run_verify']), new_test['time'],
                    new_test['test_category'], new_test['sync_count'],
                    new_test['path'])
        else:
            # Create a relative path
            path = test.replace(autotest_dir, '')
            sql = ("INSERT INTO autotests"
                  "(name, test_class, description, test_type, path, "
                  "author, dependencies, experimental, "
                  "run_verify, test_time, test_category, sync_count) "
                  "VALUES('%s','%s','%s',%d,'%s','%s','%s',%d,%d,%d,"
                  "'%s',%d)")
            sql %= (new_test['name'], new_test['test_class'], new_test['doc'],
                    int(new_test['test_type']), new_test['path'],
                    new_test['author'], new_test['dependencies'],
                    int(new_test['experimental']), int(new_test['run_verify']),
                    new_test['time'], new_test['test_category'],
                    new_test['sync_count'])

        db_execute(cursor, sql)

    add_label_dependencies(new_test_dicts, cursor)

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
        test['time'] = int(test['time'])
        if test['time'] < 1 or test['time'] > 3:
            raise Exception('Incorrect number %d for time' %
                            test['time'])
    except ValueError:
        pass

    if str == type(test['time']):
        test['time'] = test_time[test['time'].lower()]
    if str == type(test['test_type']):
        test['test_type'] = test_type[test['test_type'].lower()]

    return test


def add_label_dependencies(tests, cursor):
    """
    Look at the DEPENDENCIES field for each test and add the proper many-to-many
    relationships.
    """
    # tests may be empty so nothing to do
    if not tests:
        return

    label_name_to_id = get_id_map(cursor, 'labels', 'name')
    test_path_to_id = get_id_map(cursor, 'autotests', 'path')

    # clear out old relationships
    test_ids = ','.join(str(test_path_to_id[test['path']])
                        for test in tests)
    db_execute(cursor,
               'DELETE FROM autotests_dependency_labels WHERE test_id IN (%s)' %
               test_ids)

    value_pairs = []
    for test in tests:
        test_id = test_path_to_id[test['path']]
        for label_name in test['dependencies'].split(','):
            label_name = label_name.strip().lower()
            if not label_name:
                continue
            if label_name not in label_name_to_id:
                log_dependency_not_found(label_name)
                continue
            label_id = label_name_to_id[label_name]
            value_pairs.append('(%s, %s)' % (test_id, label_id))

    if not value_pairs:
        return

    query = ('INSERT INTO autotests_dependency_labels (test_id, label_id) '
             'VALUES ' + ','.join(value_pairs))
    db_execute(cursor, query)


def log_dependency_not_found(label_name):
    if label_name in DEPENDENCIES_NOT_FOUND:
        return
    print 'Dependency %s not found' % label_name
    DEPENDENCIES_NOT_FOUND.add(label_name)


def get_id_map(cursor, table_name, name_field):
    cursor.execute('SELECT id, %s FROM %s' % (name_field, table_name))
    name_to_id = {}
    for item_id, item_name in cursor.fetchall():
        name_to_id[item_name] = item_id
    return name_to_id


def get_tests_from_fs(parent_dir, control_pattern, add_noncompliant=False):
    """Find control jobs in location and create one big job
       Returns:
        dictionary of the form:
            tests[file_path] = parsed_object

    """
    tests = {}
    profilers = False
    if 'client/profilers' in parent_dir:
        profilers = True
    for dir in [ parent_dir ]:
        files = recursive_walk(dir, control_pattern)
        for file in files:
            if '__init__.py' in file or '.svn' in file:
                continue
            if not profilers:
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
            else:
                script = file.rstrip(".py")
                tests[file] = compiler.parseFile(file).doc
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
