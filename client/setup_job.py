# Copyright 2007 Google Inc. Released under the GPL v2
#
# Eric Li <ericli@google.com>

import logging
import os
import pickle
import re
import sys
try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client import job as client_job
from autotest.client.shared import base_job, error, packages


class setup_job(client_job.job):

    """
    setup_job is a job which runs client test setup() method at server side.

    This job is used to pre-setup client tests when development toolchain is not
    available at client.
    """

    def __init__(self, options):
        """
        Since setup_job is a client job but run on a server, it takes no control
        file as input. So client_job.__init__ is by-passed.

        @param options: an object passed in from command line OptionParser.
                        See all options defined on client/autotest.
        """
        base_job.base_job.__init__(self, options=options)
        self._cleanup_debugdir_files()
        self._cleanup_results_dir()
        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout': 3600})


def init_test(options, testdir):
    """
    Instantiate a client test object from a given test directory.

    @param options Command line options passed in to instantiate a setup_job
                   which associates with this test.
    @param testdir The test directory.
    :return: A test object or None if failed to instantiate.
    """

    locals_dict = locals().copy()
    globals_dict = globals().copy()

    locals_dict['testdir'] = testdir

    job = setup_job(options=options)
    locals_dict['job'] = job

    test_name = os.path.split(testdir)[-1]
    outputdir = os.path.join(job.resultdir, test_name)
    try:
        os.makedirs(outputdir)
    except OSError:
        pass
    locals_dict['outputdir'] = outputdir

    sys.path.insert(0, testdir)
    client_test = None
    try:
        try:
            import_stmt = 'import %s' % test_name
            init_stmt = ('auto_test = %s.%s(job, testdir, outputdir)' %
                         (test_name, test_name))
            exec import_stmt + '\n' + init_stmt in locals_dict, globals_dict
            client_test = globals_dict['auto_test']
        except ImportError, e:
            # skips error if test is control file without python test
            if re.search(test_name, str(e)):
                pass
            # give the user a warning if there is an import error.
            else:
                logging.error('%s import error: %s.  Skipping %s' %
                              (test_name, e, test_name))
        except Exception, e:
            # Log other errors (e.g., syntax errors) and collect the test.
            logging.error("%s: %s", test_name, e)
    finally:
        sys.path.pop(0)  # pop up testbindir
    return client_test


def load_all_client_tests(options):
    """
    Load and instantiate all client tests.

    This function is inspired from runtest() on client/shared/test.py.

    @param options: an object passed in from command line OptionParser.
                    See all options defined on client/autotest.

    :return: a tuple containing the list of all instantiated tests and
            a list of tests that failed to instantiate.
    """

    local_namespace = locals().copy()
    global_namespace = globals().copy()

    all_tests = []
    broken_tests = []
    for test_base_dir in ['tests', 'site_tests']:
        testdir = os.path.join(os.environ['AUTODIR'], test_base_dir)
        for test_name in os.listdir(testdir):
            client_test = init_test(options, os.path.join(testdir, test_name))
            if client_test:
                all_tests.append(client_test)
            else:
                broken_tests.append(test_name)
    if 'CUSTOM_DIR' in os.environ:
        testdir = os.environ['CUSTOM_DIR']
        for test_name in os.listdir(testdir):
            client_test = init_test(options, os.path.join(testdir, test_name))
            if client_test:
                all_tests.append(client_test)
            else:
                broken_tests.append(test_name)
    return all_tests, broken_tests


def setup_test(client_test):
    """
    Direct invoke test.setup() method.

    :return: A boolean to represent success or not.
    """

    # TODO: check if its already build. .version? hash?
    test_name = client_test.__class__.__name__
    cwd = os.getcwd()
    good_setup = False
    try:
        try:
            outputdir = os.path.join(client_test.job.resultdir, test_name)
            try:
                os.makedirs(outputdir)
                os.chdir(outputdir)
            except OSError:
                pass
            logging.info('setup %s.' % test_name)
            client_test.setup()

            # Touch .version file under src to prevent further setup on client
            # host. See client/shared/utils.py update_version()
            if os.path.exists(client_test.srcdir):
                versionfile = os.path.join(client_test.srcdir, '.version')
                pickle.dump(client_test.version, open(versionfile, 'w'))
            good_setup = True
        except Exception, err:
            logging.error(err)
            raise error.AutoservError('Failed to build client test %s on '
                                      'server.' % test_name)
    finally:
        # back to original working dir
        os.chdir(cwd)
    return good_setup


def setup_tests(options):
    """
    Load and instantiate all client tests.

    This function is inspired from runtest() on client/shared/test.py.

    @param options: an object passed in from command line OptionParser.
                    See all options defined on client/autotest.
    """

    assert options.client_test_setup, 'Specify prebuild client tests on the ' \
                                      'command line.'

    requested_tests = options.client_test_setup.split(',')
    candidates, broken_tests = load_all_client_tests(options)

    failed_tests = []
    if 'all' in requested_tests:
        need_to_setup = candidates
        failed_tests += broken_tests
    else:
        need_to_setup = []
        for candidate in candidates:
            if candidate.__class__.__name__ in requested_tests:
                need_to_setup.append(candidate)
        for broken_test in broken_tests:
            if broken_test in requested_tests:
                failed_tests.append(broken_test)

    if need_to_setup:
        cwd = os.getcwd()
        os.chdir(need_to_setup[0].job.clientdir)
        os.system('tools/make_clean')
        os.chdir(cwd)
    elif not failed_tests:
        logging.error('### No test setup candidates ###')
        raise error.AutoservError('No test setup candidates.')

    for client_test in need_to_setup:
        good_setup = setup_test(client_test)
        if not good_setup:
            failed_tests.append(client_test.__class__.__name__)

    logging.info('############################# SUMMARY '
                 '#############################')

    # Print out tests that failed
    if failed_tests:
        logging.info('Finished setup -- The following tests failed')
        for failed_test in failed_tests:
            logging.info(failed_test)
    else:
        logging.info('Finished setup -- All tests built successfully')
    logging.info('######################### END SUMMARY '
                 '##############################')
    if failed_tests:
        raise error.AutoservError('Finished setup with errors.')
