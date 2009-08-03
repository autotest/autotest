import time
from autotest_lib.client.bin import test

class barriertest(test.test):
    version = 1


    def execute(self, timeout_sync, timeout_start, timeout_stop,
                    hostid, masterid, all_ids):
        profilers = self.job.profilers

        b0 = self.job.barrier(hostid, "sync_profilers", timeout_start,
                              port=11920)
        b0.rendezvous_servers(masterid, hostid)

        b1 = self.job.barrier(hostid, "start_profilers", timeout_start,
                              port=11920)
        b1.rendezvous_servers(masterid, hostid)

        b2 = self.job.barrier(hostid, "local_sync_profilers", timeout_sync)
        b2.rendezvous(*all_ids)

        profilers.start(self)

        b3 = self.job.barrier(hostid, "stop_profilers", timeout_stop,
                              port=11920)
        b3.rendezvous_servers(masterid, hostid)

        profilers.stop(self)
        profilers.report(self)
