#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.
"""
This utility allows for easy updating, removing and importing
of tests into the autotest_web afe_autotests table.

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


import common
import logging, re, os, sys, optparse, compiler
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import models
from autotest_lib.client.common_lib import control_data


logging.basicConfig(level=logging.DEBUG)
# Global
DRY_RUN = False
DEPENDENCIES_NOT_FOUND = set()


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
    for test in models.Test.objects.all():
        full_path = os.path.join(autotest_dir, test.path)
        if not os.path.isfile(full_path):
            if verbose:
                print "Removing " + test.path
            _log_or_execute(repr(test), test.delete)

    # Find profilers that are no longer present
    for profiler in models.Profiler.objects.all():
        full_path = os.path.join(autotest_dir, "client", "profilers",
                                 profiler.name)
        if not os.path.exists(full_path):
            if verbose:
                print "Removing " + profiler.name
            _log_or_execute(repr(profiler), profiler.delete)


def update_profilers_in_db(profilers, verbose=False, description='NA',
                           add_noncompliant=False):
    """Update profilers in autotest_web database"""
    for profiler in profilers:
        name = os.path.basename(profiler).rstrip(".py")
        if not profilers[profiler]:
            if add_noncompliant:
                doc = description
            else:
                print "Skipping %s, missing docstring" % profiler
        else:
            doc = profilers[profiler]

        model = models.Profiler.objects.get_or_create(name=name)[0]
        model.description = doc
        _log_or_execute(repr(model), model.save)


def update_tests_in_db(tests, dry_run=False, add_experimental=False,
                       add_noncompliant=False, verbose=False,
                       autotest_dir=None):
    """Update or add each test to the database"""
    for test in tests:
        new_test = models.Test.objects.get_or_create(
                path=test.replace(autotest_dir, '').lstrip('/'))[0]
        if verbose:
            print "Processing " + new_test.path

        # Set the test's attributes
        data = tests[test]
        _set_attributes_clean(new_test, data)

        # This only takes place if --add-noncompliant is provided on the CLI
        if not new_test.name:
            test_new_test = test.split('/')
            if test_new_test[-1] == 'control':
                new_test.name = test_new_test[-2]
            else:
                control_name = "%s:%s"
                control_name %= (test_new_test[-2],
                                 test_new_test[-1])
                new_test.name = control_name.replace('control.', '')

        # Experimental Check
        if not add_experimental and new_test.experimental:
            continue

        _log_or_execute(repr(new_test), new_test.save)
        add_label_dependencies(new_test)


def _set_attributes_clean(test, data):
    """Sets the attributes of the Test object"""

    test_type = { 'client' : 1,
                  'server' : 2, }
    test_time = { 'short' : 1,
                  'medium' : 2,
                  'long' : 3, }


    string_attributes = ('name', 'author', 'test_class', 'test_category',
                         'test_category', 'sync_count')
    for attribute in string_attributes:
        setattr(test, attribute, getattr(data, attribute))

    test.description = data.doc
    test.dependencies = ", ".join(data.dependencies)

    int_attributes = ('experimental', 'run_verify')
    for attribute in int_attributes:
        setattr(test, attribute, int(getattr(data, attribute)))

    try:
        test.test_type = int(data.test_type)
        if test.test_type != 1 and test.test_type != 2:
            raise Exception('Incorrect number %d for test_type' %
                            test.test_type)
    except ValueError:
        pass
    try:
        test.test_time = int(data.time)
        if test.test_time < 1 or test.time > 3:
            raise Exception('Incorrect number %d for time' % test.time)
    except ValueError:
        pass

    if not test.test_time and str == type(data.time):
        test.test_time = test_time[data.time.lower()]
    if not test.test_type and str == type(data.test_type):
        test.test_type = test_type[data.test_type.lower()]


def add_label_dependencies(test):
    """
    Look at the DEPENDENCIES field for each test and add the proper many-to-many
    relationships.
    """
    # clear out old relationships
    _log_or_execute(repr(test), test.dependency_labels.clear,
                    subject='clear dependencies from')

    for label_name in test.dependencies.split(','):
        label_name = label_name.strip().lower()
        if not label_name:
            continue

        try:
            label = models.Label.objects.get(name=label_name)
        except models.Label.DoesNotExist:
            log_dependency_not_found(label_name)
            continue

        _log_or_execute(repr(label), test.dependency_labels.add, label,
                        subject='add dependency to %s' % test.name)


def log_dependency_not_found(label_name):
    if label_name in DEPENDENCIES_NOT_FOUND:
        return
    print 'Dependency %s not found' % label_name
    DEPENDENCIES_NOT_FOUND.add(label_name)


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


def _log_or_execute(content, func, *args, **kwargs):
    """Log a message if dry_run is enabled, or execute the given function

    @param content the actual log message
    @param func function to execute if dry_run is not enabled
    @param subject (Optional) The type of log being written. Defaults to the
                   name of the provided function.
    """
    subject = kwargs.get('subject', func.__name__)

    if DRY_RUN:
        print 'Would %s: %s' % (subject, content)
    else:
        func(*args)


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


if __name__ == "__main__":
    main(sys.argv)
