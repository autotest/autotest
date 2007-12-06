import test, os_dep
from autotest_utils import *

class btreplay(test.test):
	version = 1

	# http://brick.kernel.dk/snaps/blktrace-git-latest.tar.gz
	def setup(self, tarball = 'blktrace-git-latest.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)

		self.job.setup_dep(['libaio'])
		libs = '-L' + self.autodir + '/deps/libaio/lib -laio'
		cflags = '-I ' + self.autodir + '/deps/libaio/include'
		var_libs = 'LIBS="' + libs + '"'
		var_cflags  = 'CFLAGS="' + cflags + '"'
		self.make_flags = var_libs + ' ' + var_cflags

		os.chdir(self.srcdir)
		system('patch -p1 < ../Makefile.patch')
		system(self.make_flags + ' make')


	def initialize(self):
		self.ldlib = 'LD_LIBRARY_PATH=%s/deps/libaio/lib'%(self.autodir)


	def execute(self, iterations = 1, dev="md_d1", devices="",
			extra_args = '', tmpdir = None):
		if not tmpdir:
			tmpdir = self.tmpdir

		args = "%s \"%s\" %s" %(dev,devices,tmpdir)
		os.chdir(self.srcdir)
		cmd = self.ldlib + ' ../run_btreplay.sh ' + args + ' ' + extra_args

		profilers = self.job.profilers
		if not profilers.only():
			for i in range(iterations):
				system(cmd)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			system(cmd)
			profilers.stop(self)
			profilers.report(self)

		self.__format_results(open(self.debugdir + '/stdout').read())


	def __format_results(self, results):
		out = open(self.resultsdir + '/keyval', 'w')
		lines = results.split('\n')

		for n in range(len(lines)):
			if lines[n].strip() == "==================== All Devices ====================":
				words = lines[n-2].split()
				s = words[1].strip('sytem').split(':')
				e = words[2].strip('elapsd').split(':')
				break

		systime = 0.0
		for n in range(len(s)):
			i = (len(s)-1) - n
			systime += float(s[i])*(60**n)
		elapsed = 0.0
		for n in range(len(e)):
			i = (len(e)-1) - n
			elapsed += float(e[i])*(60**n)

		q2c = 0.0
		for line in lines:
			words = line.split()
			if len(words) < 3:
				continue
			if words[0] == 'Q2C':
				q2c = float(words[2])
				break

		
		print >> out, """\
time=%f
systime=%f
avg_q2c_latency=%f
""" % (elapsed, systime, q2c)
		out.close()
