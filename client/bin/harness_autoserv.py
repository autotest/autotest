import os

from autotest_lib.client.bin import harness


class harness_autoserv(harness.harness):
    """
    The server harness for running from autoserv

    Properties:
            job
                    The job object for this job
    """

    def __init__(self, job):
        """
                job
                        The job object for this job
        """
        super(harness_autoserv, self).__init__(job)
        self.status = os.fdopen(3, 'w')

        # initialize a named pipe to use for signaling
        self.fifo_path = os.path.join(job.autodir, "autoserv.fifo")
        if not os.path.exists(self.fifo_path):
            os.mkfifo(self.fifo_path)


    def run_test_complete(self):
        """A test run by this job is complete, signal it to autoserv and
        wait for it to signal to continue"""
        # signal test completion to the server
        if self.status:
            self.status.write("AUTOTEST_TEST_COMPLETE\n")
            self.status.flush()

        # wait for the server to signal back to us
        fifo = open(self.fifo_path)
        fifo.read(1)
        fifo.close()


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
