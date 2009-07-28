import os

from autotest_lib.client.common_lib import autotemp
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


    def _send_and_wait(self, title, *args):
        """Send a message to the autoserv and wait for it to signal
        completion.

        @param title: An alphanumeric string to title the message.
        @param *args: Additional arbitrary alphanumeric arguments to pass
                to the server.
        """
        # create a named pipe for us to recieve a signal on
        fifo_dir = autotemp.tempdir(suffix='-fifo', unique_id='harness',
                                    dir=self.job.tmpdir)
        try:
            fifo_path = os.path.join(fifo_dir.name, 'autoserv.fifo')
            os.mkfifo(fifo_path)

            # send signal to the server as title[:args]:path
            msg = ':'.join([title] + list(args) + [fifo_path]) + '\n'
            self.status.write(msg)

            # wait for the server to signal back to us
            fifo = open(fifo_path)
            fifo.read(1)
            fifo.close()
        finally:
            fifo_dir.clean()


    def run_test_complete(self):
        """A test run by this job is complete, signal it to autoserv and
        wait for it to signal to continue"""
        self._send_and_wait('AUTOTEST_TEST_COMPLETE')


    def test_status(self, status, tag):
        """A test within this job is completing"""
        for line in status.split('\n'):
            # sent status messages with AUTOTEST_STATUS:tag:message
            msg = 'AUTOTEST_STATUS:%s:%s\n'
            msg %= (tag, line)
            self.status.write(msg)
