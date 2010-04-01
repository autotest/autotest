# This is used directly by server/tests/barriertest/control.srv

import logging, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import barrier


class barriertest(test.test):
    version = 2


    def run_once(self, our_addr, hostnames, master):
        # A reusable local server as we're using multiple barriers in one test.
        server = barrier.listen_server()

        # Basic barrier rendezvous test.
        self.job.barrier(our_addr, 'First', timeout=60, listen_server=server
                         ).rendezvous(*hostnames)
        logging.info('1. rendezvous "First" complete.')
        time.sleep(2)

        # A rendezvous_servers using a different master than the default.
        self.job.barrier(our_addr, 'Second', timeout=60, listen_server=server
                         ).rendezvous_servers(hostnames[-1], *hostnames[:-1])
        logging.info('2. rendezvous_servers "Second" complete.')
        time.sleep(2)

        # A regular rendezvous, this time testing the abort functionality.
        try:
            self.job.barrier(our_addr, 'Third', timeout=60,
                             listen_server=server
                             ).rendezvous(abort=True, *hostnames)
        except barrier.BarrierAbortError:
            pass
        else:
            raise error.TestFail('Explicit barrier rendezvous abort failed.')
        logging.info('3. rendezvous(abort=True) "Third" complete.')
        time.sleep(2)

        # Now attempt a rendezvous_servers that also includes the server.
        self.job.barrier(our_addr, 'Final', timeout=60, listen_server=server
                         ).rendezvous_servers(master, *hostnames)
        logging.info('N. rendezvous_servers "Final" complete.')
        time.sleep(2)

        server.close()
