import test
from autotest_utils import *
from subprocess import *

class bash_shared_mapping(test.test):
	version = 3

	# http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
	def setup(self, tarball = 'ext3-tools.tar.gz'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)

		os.chdir(self.srcdir)
		system('make bash-shared-mapping usemem')


	def execute(self, testdir = None):
		if not testdir:
			testdir = self.tmpdir
		os.chdir(testdir)
		file = os.path.join(testdir, 'foo')
		# Want to use twice total memsize
		kilobytes = 2 * memtotal()

		# Want two usemem -m megabytes in parallel in background.
		# Really need them to loop until they exit. then clean up.
		usemem = "%s/usemem -m %d" % (self.srcdir, kilobytes / 1024)
		Popen(usemem, shell=True)
		Popen(usemem, shell=True)

		cmd = "%s/bash-shared-mapping %s %d -t %d" % \
				(self.srcdir, file, kilobytes, count_cpus())
		Popen(cmd, shell=True)

