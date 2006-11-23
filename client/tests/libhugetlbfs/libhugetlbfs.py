import test, re
from autotest_utils import *

class libhugetlbfs(test.test):
	version = 1

	# http://prdownloads.sourceforge.net/libhugetlbfs/libhugetlbfs-1.0-pre4-1.tar.gz?download
	def setup(self, tarball = 'libhugetlbfs-1.0-pre4-1.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, dir, pages_requested = 20):
		# Check kernel version, should >= 2.6.16
		version = system_output('uname -r')
		(major, minor, sub) = re.split(r'[.-]', version)[0:3]
		if int(major) < 2 or int(minor) < 6 or int(sub) < 16:
			raise TestError('Kernel version %s < 2.6.16' % version)
		
		# Check huge page number
		system('echo %d > /proc/sys/vm/nr_hugepages' % pages_requested, 1)
		pages_available = 0
		if os.path.exists('/proc/sys/vm/nr_hugepages'):
			pages_available = int(open('/proc/sys/vm/nr_hugepages', 'r').readline())
		# if pages == 0:
		# 	raise TestError('No huge pages allocated, exiting test')
		if pages_available < pages_requested:
			raise TestError('%d huge pages available, < %d pages requested' % (pages_available, pages_requested))
		
		# Check if hugetlbfs has been mounted
		if not file_contains_pattern('/proc/mounts', 'hugetlbfs'):
			system('mount -t hugetlbfs none %s' % dir)
		
		os.chdir(self.srcdir)
		system('make check')

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			os.chdir(self.srcdir)
			system('make check')
			profilers.stop(self)
			profilers.report(self)

		system('umount %s' % dir)
