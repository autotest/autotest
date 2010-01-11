"""The harness interface

The interface between the client and the server when hosted.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

import os, sys
import common

class harness(object):
    """The NULL server harness

    Properties:
            job
                    The job object for this job
    """

    def __init__(self, job):
        """
                job
                        The job object for this job
        """
        self.setup(job)


    def setup(self, job):
        """
                job
                        The job object for this job
        """
        self.job = job

        configd = os.path.join(os.environ['AUTODIR'], 'configs')
        if os.path.isdir(configd):
            (name, dirs, files) = os.walk(configd).next()
            job.config_set('kernel.default_config_set',
                           [ configd + '/' ] + files)


    def run_start(self):
        """A run within this job is starting"""
        pass


    def run_pause(self):
        """A run within this job is completing (expect continue)"""
        pass


    def run_reboot(self):
        """A run within this job is performing a reboot
           (expect continue following reboot)
        """
        pass


    def run_abort(self):
        """A run within this job is aborting. It all went wrong"""
        pass


    def run_complete(self):
        """A run within this job is completing (all done)"""
        pass


    def run_test_complete(self):
        """A test run by this job is complete. Note that if multiple
        tests are run in parallel, this will only be called when all
        of the parallel runs complete."""
        pass


    def test_status(self, status, tag):
        """A test within this job is completing"""
        pass


    def test_status_detail(self, code, subdir, operation, status, tag):
        """A test within this job is completing (detail)"""
        pass


def select(which, job):
    if not which:
        which = 'standalone'

    harness_name = 'harness_%s' % which
    harness_module = common.setup_modules.import_module(harness_name,
                                                        'autotest_lib.client.bin')
    harness_instance = getattr(harness_module, harness_name)(job)

    return harness_instance
