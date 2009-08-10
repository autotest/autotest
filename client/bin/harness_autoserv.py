import os, logging
from autotest_lib.client.common_lib import autotemp, base_packages, error
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


    def run_start(self):
        # set up the package fetcher for direct-from-autoserv fetches
        fetcher = AutoservFetcher(self.job.pkgmgr, self)
        self.job.pkgmgr.add_repository(fetcher)


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


    def fetch_package(self, pkg_name, dest_path):
        """Request a package from the remote autoserv.

        @param pkg_name: The name of the package, as generally used by the
                client.common_lib.packages infrastructure.
        @param dest_path: The path the package should be copied to.
        """
        self._send_and_wait('AUTOTEST_FETCH_PACKAGE', pkg_name, dest_path)


class AutoservFetcher(base_packages.RepositoryFetcher):
    def __init__(self, package_manager, job_harness):
        self.url = "autoserv://"
        self.job_harness = job_harness


    def fetch_pkg_file(self, filename, dest_path):
        logging.info('Fetching %s from autoserv to %s', filename, dest_path)
        self.job_harness.fetch_package(filename, dest_path)
        if os.path.exists(dest_path):
            logging.debug('Successfully fetched %s from autoserv', filename)
        else:
            raise error.PackageFetchError('%s not fetched from autoserv'
                                          % filename)
