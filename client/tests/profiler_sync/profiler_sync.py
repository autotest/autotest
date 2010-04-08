# This "test" is used by autotest_lib.server.standalone_profilers to start
# and stop profilers on a collection of hosts at approximately the same
# time by synchronizing using barriers.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import barrier

class profiler_sync(test.test):
    version = 1


    def execute(self, timeout_sync, timeout_start, timeout_stop,
                hostid, masterid, all_ids):
        """
        @param timeout_sync: Seconds to wait for the synchronization of all
                hosts that will be launching profilers. (local_sync_profilers)
        @param timeout_start: Seconds to wait for each of the initial
                sync_profilers and start_profilers barriers between this
                host and the master to be reached.
        @param timeout_stop: Seconds to wait for this host and the master to
                reach each of the stop_profilers and finish_profilers barriers.
        @param hostid: This host's id (typically the hostname).
        @param masterid: The master barrier host id where autoserv is running.
        @param all_ids: A list of all hosts to synchronize profilers on.
        """
        profilers = self.job.profilers

        barrier_server = barrier.listen_server(port=11920)
        b0 = self.job.barrier(hostid, "sync_profilers", timeout_start,
                              listen_server=barrier_server)
        b0.rendezvous_servers(masterid, hostid)

        b1 = self.job.barrier(hostid, "start_profilers", timeout_start,
                              listen_server=barrier_server)
        b1.rendezvous_servers(masterid, hostid)

        b2 = self.job.barrier(hostid, "local_sync_profilers", timeout_sync)
        b2.rendezvous(*all_ids)

        profilers.start(self)

        b3 = self.job.barrier(hostid, "stop_profilers", timeout_stop,
                              listen_server=barrier_server)
        b3.rendezvous_servers(masterid, hostid)

        profilers.stop(self)
        profilers.report(self)

        b4 = self.job.barrier(hostid, "finish_profilers", timeout_stop,
                              listen_server=barrier_server)
        b4.rendezvous_servers(masterid, hostid)

        barrier_server.close()
