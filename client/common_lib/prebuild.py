# Copyright 2010 Google Inc. Released under the GPL v2
#
# Eric Li <ericli@google.com>

import logging, os, pickle, re, sys
import common
from autotest_lib.client.bin import setup_job as client_setup_job


def touch_init(parent_dir, child_dir):
    """
    Touch __init__.py file all alone through from dir_patent to child_dir.

    So client tests could be loaded as Python modules. Assume child_dir is a
    subdirectory of parent_dir.
    """

    if not child_dir.startswith(parent_dir):
        logging.error('%s is not a subdirectory of %s' % (child_dir,
                                                          parent_dir))
        return
    sub_parent_dirs = parent_dir.split(os.path.sep)
    sub_child_dirs = child_dir.split(os.path.sep)
    for sub_dir in sub_child_dirs[len(sub_parent_dirs):]:
        sub_parent_dirs.append(sub_dir)
        path = os.path.sep.join(sub_parent_dirs)
        init_py = os.path.join(path, '__init__.py')
        open(init_py, 'a').close()


def init_test(testdir):
    """
    Instantiate a client test object from a given test directory.

    @param testdir The test directory.
    @returns A test object or None if failed to instantiate.
    """

    class options:
        tag = ''
        verbose = None
        cont = False
        harness = 'autoserv'
        hostname = None
        user = None
        log = True
    return client_setup_job.init_test(options, testdir)


def setup(autotest_client_dir, client_test_dir):
    """
    Setup prebuild of a client test.

    @param autotest_client_dir: The autotest/client base directory.
    @param client_test_dir: The actual test directory under client.
    """

    os.environ['AUTODIR'] = autotest_client_dir
    touch_init(autotest_client_dir, client_test_dir)

    # instantiate a client_test instance.
    client_test = init_test(client_test_dir)
    client_setup_job.setup_test(client_test)
