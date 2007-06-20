import test, os_dep
from autotest_utils import *

class bonnie(test.test):
	version = 1

	# http://www.coker.com.au/bonnie++/bonnie++-1.03a.tgz
	def setup(self, tarball = 'bonnie++-1.03a.tgz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		os_dep.command('g++')
		system('./configure')
		system('make')

	def execute(self, iterations = 1, extra_args = '', user = 'root'):
		args = '-d ' + self.tmpdir + ' -u ' + user + ' ' + extra_args

		for i in range(iterations):
			system(self.srcdir + '/bonnie++ ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/bonnie++ ' + args)
			profilers.stop(self)
			profilers.report(self)

		self.__format_results(open(self.debugdir + '/stdout').read())

	def __format_results(self, results):
		out = open(self.resultsdir + '/keyval', 'w')
		for line in results.split('\n'):
			if len([c for c in line if c == ',']) != 26:
				continue
			fields = tuple(line.split(','))
		print >> out, """size=%s
seqout_perchr_ksec=%s
seqout_perchr_pctcp=%s
seqout_perblk_ksec=%s
seqout_perblk_pctcp=%s
seqout_rewrite_ksec=%s
seqout_rewrite_pctcp=%s
seqin_perchr_ksec=%s
seqin_perchr_pctcp=%s
seqin_perblk_ksec=%s
seqin_perblk_pctcp=%s
rand_ksec=%s
rand_pctcp=%s
files=%s
seqcreate_create_ksec=%s
seqcreate_create_pctcp=%s
seqcreate_read_ksec=%s
seqcreate_read_pctcp=%s
seqcreate_delete_ksec=%s
seqcreate_delete_pctcp=%s
randreate_create_ksec=%s
randcreate_create_pctcp=%s
randcreate_read_ksec=%s
randcreate_read_pctcp=%s
randcreate_delete_ksec=%s
randcreate_delete_pctcp=%s
""" % fields[1:]
		out.close()
