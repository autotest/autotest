import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class linus_stress(test.test):
	version = 1

	def setup(self):
		os.mkdir(self.srcdir)
		os.chdir(self.bindir)
		utils.system('cp linus_stress.c src/')
		os.chdir(self.srcdir)
		utils.system('cc linus_stress.c -D_POSIX_C_SOURCE=200112 -o linus_stress')


	def run_the_test(self, iterations):
		write_one_line('/proc/sys/vm/dirty_ratio', '4')
		write_one_line('/proc/sys/vm/dirty_background_ratio', '2')

		cmd = os.path.join(self.srcdir, 'linus_stress')
		args = "%d" % (memtotal() / 32)

		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)

		for i in range(iterations):
			utils.system(cmd + ' ' + args)

		if profilers.present():
			profilers.stop(self)
			profilers.report(self)


	def execute(self, iterations = 1):
		dirty_ratio = autotest_utils.read_one_line('/proc/sys/vm/dirty_ratio')
		dirty_background_ratio = autotest_utils.read_one_line('/proc/sys/vm/dirty_background_ratio')
		try:
			self.run_the_test(iterations)
		finally:
			autotest_utils.write_one_line('/proc/sys/vm/dirty_ratio', dirty_ratio)
			autotest_utils.write_one_line('/proc/sys/vm/dirty_background_ratio', dirty_background_ratio)
