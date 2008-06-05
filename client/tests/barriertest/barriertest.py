import time
from autotest_utils.client.bin import test

class barriertest(test.test):
	version = 1


	def execute(self, timeout_sync, timeout_start, timeout_stop,
			hostid, masterid, all_ids):
		profilers = self.job.profilers

		b0 = self.job.barrier(hostid, "sync_profilers",
			timeout_start, port=63100)
		b0.rendevous_servers(masterid, hostid)

		b1 = self.job.barrier(hostid, "start_profilers",
			timeout_start, port=63100)
		b1.rendevous_servers(masterid, hostid)

		b2 = self.job.barrier(hostid, "local_sync_profilers",
			timeout_sync)
		b2.rendevous(*all_ids)

		profilers.start(self)

		b3 = self.job.barrier(hostid, "stop_profilers",
			timeout_stop, port=63100)
		b3.rendevous_servers(masterid, hostid)

		profilers.stop(self)
		profilers.report(self)
