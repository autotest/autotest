import test
from autotest_utils import *

class fio(test.test):
	version = 2

	# http://brick.kernel.dk/snaps/fio-1.15.tar.bz2
	def setup(self, tarball = 'fio-1.15.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)

		self.job.setup_dep(['libaio'])
		ldflags = '-L' + self.autodir + '/deps/libaio/lib'
		cflags = '-I' + self.autodir + '/deps/libaio/include'
		var_ldflags = 'LDFLAGS="' + ldflags + '"'
		var_cflags  = 'CFLAGS="' + cflags + '"'

		os.chdir(self.srcdir)
		system('patch -p1 < ../Makefile.patch')
		system('%s %s make' % (var_ldflags, var_cflags))

	def execute(self, args = '', user = 'root'):
		os.chdir(self.srcdir)
		##vars = 'TMPDIR=\"%s\" RESULTDIR=\"%s\"' % (self.tmpdir, self.resultsdir)
		vars = 'LD_LIBRARY_PATH="' + self.autodir + '/deps/libaio/lib"'
		##args = '-m -o ' + self.resultsdir + '/fio-tio.log ' + self.srcdir + '/examples/tiobench-example';
		args = '--output ' + self.resultsdir + '/fio-mixed.log ' + self.bindir + '/fio-mixed.job';
		system(vars + ' ./fio ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(vars + ' ./fio ' + args)
			profilers.stop(self)
			profilers.report(self)
