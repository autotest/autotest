"""
The simple harness interface
"""

__author__ = """Copyright Andy Whitcroft, Martin J. Bligh 2006"""

import os, harness, time

class harness_simple(harness.harness):
    """
    The simple server harness

    Properties:
            job
                    The job object for this job
    """

    def __init__(self, job, harness_args):
        """
                job
                        The job object for this job
        """
        self.setup(job)

        self.status = os.fdopen(3, 'w')


    def test_status(self, status, tag):
        """A test within this job is completing"""
        if self.status:
            for line in status.split('\n'):
                # prepend status messages with
                # AUTOTEST_STATUS:tag: so that we can tell
                # which lines were sent by the autotest client
                pre = 'AUTOTEST_STATUS:%s:' % (tag,)
                self.status.write(pre + line + '\n')
                self.status.flush()
