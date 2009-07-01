import os, tempfile

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
        self.status = os.fdopen(3, 'w', 0)


    def run_test_complete(self):
        """A test run by this job is complete, signal it to autoserv and
        wait for it to signal to continue"""
        # create a named pipe for us to receive a signal on
        fifo_dir = tempfile.mkdtemp(suffix="-fifo", dir=self.job.tmpdir)
        fifo_path = os.path.join(fifo_dir, "autoserv.fifo")
        os.mkfifo(fifo_path)

        # signal test completion to the server as
        # AUTOTEST_TEST_COMPLETE:path
        msg = "AUTOTEST_TEST_COMPLETE:%s\n"
        msg %= fifo_path
        self.status.write(msg)

        # wait for the server to signal back to us
        fifo = open(fifo_path)
        fifo.read(1)
        fifo.close()

        # clean up the named pipe
        os.remove(fifo_path)
        os.rmdir(fifo_dir)


    def test_status(self, status, tag):
        """A test within this job is completing"""
        for line in status.split('\n'):
            # sent status messages with AUTOTEST_STATUS:tag:message
            msg = "AUTOTEST_STATUS:%s:%s\n"
            msg %= (tag, line)
            self.status.write(msg)
