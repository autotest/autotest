import test, time
from autotest_utils import *

class barriertest(test.test):
	version = 1


	def execute(self, timeout_sync, timeout_start, timeout_stop,
			hostid, masterid, all_ids):
		profilers = self.job.profilers

		b1 = self.job.barrier(hostid, "sync_profilers",
			timeout_sync)
		b1.rendevous(*all_ids)

		profilers.start(self)
		b2 = self.job.barrier(hostid, "start_profilers",
			timeout_start, 63100)
		b2.rendevous_servers(masterid)

		b3 = self.job.barrier(hostid, "stop_profilers",
			timeout_stop, 63100)
		b3.rendevous_servers(masterid)

		profilers.stop(self)
		profilers.report(self)
