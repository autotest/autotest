# This is used directly by server/tests/barriertest/control.srv

import logging, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import barrier, error


class barriertest(test.test):
    version = 2


    def run_once(self, our_addr, hostnames, master, timeout=120):
        # A reusable local server as we're using multiple barriers in one test.
        server = barrier.listen_server()

        # Basic barrier rendezvous test.
        self.job.barrier(our_addr, 'First', timeout=timeout,
                         listen_server=server).rendezvous(*hostnames)
        logging.info('1. rendezvous "First" complete.')
        time.sleep(2)

        # A rendezvous_servers using a different master than the default.
        self.job.barrier(our_addr, 'Second', timeout=timeout,
                         listen_server=server
                         ).rendezvous_servers(hostnames[-1], *hostnames[:-1])
        logging.info('2. rendezvous_servers "Second" complete.')
        time.sleep(2)

        # A regular rendezvous, this time testing the abort functionality.
        try:
            self.job.barrier(our_addr, 'WillAbort', timeout=timeout,
                             listen_server=server
                             ).rendezvous(abort=True, *hostnames)
        except error.BarrierAbortError:
            pass
        except error.BarrierError, e:
            # We did get an error from the barrier, but was is acceptable or
            # not?  Site code may not be able to indicate an explicit abort.
            self.job.record('WARN', None, 'barriertest',
                            'BarrierError %s instead of BarrierAbortError.' % e)
        else:
            raise error.TestFail('Explicit barrier rendezvous abort failed.')
        logging.info('3. rendezvous(abort=True) complete.')
        time.sleep(2)

        # Now attempt a rendezvous_servers that also includes the server.
        self.job.barrier(our_addr, 'FinalSync', timeout=timeout,
                         listen_server=server
                         ).rendezvous_servers(master, *hostnames)
        logging.info('4. rendezvous_servers "FinalSync" complete.')
        time.sleep(2)

        # rendezvous_servers, aborted from the master.
        try:
            self.job.barrier(our_addr, 'WillAbortServers', timeout=timeout,
                             listen_server=server
                             ).rendezvous_servers(master, *hostnames)
        except error.BarrierAbortError:
            pass
        except error.BarrierError, e:
            # We did get an error from the barrier, but was is acceptable or
            # not?  Site code may not be able to indicate an explicit abort.
            self.job.record('WARN', None, 'barriertest',
                            'BarrierError %s instead of BarrierAbortError.' % e)
        else:
            raise error.TestFail('Explicit barrier rendezvous abort failed.')
        logging.info('5. rendezvous_servers(abort=True) complete.')
        time.sleep(2)

        server.close()
