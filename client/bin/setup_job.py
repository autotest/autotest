# Copyright 2007 Google Inc. Released under the GPL v2
#
# Eric Li <ericli@google.com>

import logging, os, pickle, sys
import common

from autotest_lib.client.bin import client_logging_config
from autotest_lib.client.bin import job as client_job
from autotest_lib.client.common_lib import base_job
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import logging_manager
from autotest_lib.client.common_lib import packages


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
                        See all options defined on client/bin/autotest.
        """
        base_job.base_job.__init__(self, options=options)
        logging_manager.configure_logging(
            client_logging_config.ClientLoggingConfig(),
            results_dir=self.resultdir,
            verbose=options.verbose)
        self._cleanup_results_dir()
        self.pkgmgr = packages.PackageManager(
            self.autodir, run_function_dargs={'timeout':3600})


def load_all_client_tests(options):
    """
    Load and instantiate all client tests.

    This function is inspired from runtest() on client/common_lib/test.py.

    @param options: an object passed in from command line OptionParser.
                    See all options defined on client/bin/autotest.
    """

    local_namespace = locals().copy()
    global_namespace = globals().copy()

    all_tests = []
    for test_base_dir in ['tests', 'site_tests']:
        testdir = os.path.join(os.environ['AUTODIR'], test_base_dir)
        for test_name in os.listdir(testdir):
            job = setup_job(options=options)
            testbindir = os.path.join(testdir, test_name)
            local_namespace['testbindir'] = testbindir

            outputdir = os.path.join(job.resultdir, test_name)
            try:
                os.makedirs(outputdir)
            except OSError:
                pass

            local_namespace['job'] = job
            local_namespace['outputdir'] = outputdir

            sys.path.insert(0, testbindir)
            try:
                try:
                    exec("import %s" % test_name, local_namespace,
                         global_namespace)
                    exec("auto_test = %s.%s(job, testbindir, outputdir)" %
                         (test_name, test_name), local_namespace,
                         global_namespace)
                    client_test = global_namespace['auto_test']
                    all_tests.append(client_test)
                except ImportError:
                    # this test has only control file but no python.
                    pass
            finally:
                sys.path.pop(0) # pop up testbindir
    return all_tests


def setup_tests(options):
    """
    Load and instantiate all client tests.

    This function is inspired from runtest() on client/common_lib/test.py.

    @param options: an object passed in from command line OptionParser.
                    See all options defined on client/bin/autotest.
    """

    assert options.client_test_setup, 'Specify prebuild client tests on the ' \
                                      'command line.'

    requested_tests = options.client_test_setup.split(',')
    candidates = load_all_client_tests(options)

    if options.client_test_setup.lower().find('all') >= 0:
        need_to_setup = candidates
    else:
        need_to_setup = []
        for candidate in candidates:
            if candidate.__class__.__name__ in requested_tests:
                need_to_setup.append(candidate)

    if need_to_setup:
        cwd = os.getcwd()
        os.chdir(need_to_setup[0].job.clientdir)
        os.system('tools/make_clean')
        os.chdir(cwd)

    failed_tests = []
    for setup_test in need_to_setup:
        test_name = setup_test.__class__.__name__
        try:
            outputdir = os.path.join(setup_test.job.resultdir, test_name)
            try:
                os.makedirs(outputdir)
                os.chdir(outputdir)
            except OSError:
                pass
            logging.info('setup %s.' % test_name)
            setup_test.setup()
            # Touch .version file under src to prevent further setup on client
            # host. See client/common_lib/utils.py update_version()
            if os.path.exists(setup_test.srcdir):
                versionfile = os.path.join(setup_test.srcdir, '.version')
                pickle.dump(setup_test.version, open(versionfile, 'w'))
        except Exception, err:
            logging.error(err)
            failed_tests.append(test_name)

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
