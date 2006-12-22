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
		if re.split(r'[.-]', version)[0:3] < ['2', '6', '16']:
			raise TestError('Kernel version %s < 2.6.16' % version)
		
		# Check huge page number
		pages_available = 0
		if os.path.exists('/proc/sys/vm/nr_hugepages'):
			system('echo %d > /proc/sys/vm/nr_hugepages' % \
							pages_requested)
			pages_available = int(open('/proc/sys/vm/nr_hugepages', 'r').readline())
		else:
			raise TestError('Kernel does not support hugepages')
		if pages_available < pages_requested:
			raise TestError('%d huge pages available, < %d pages requested' % (pages_available, pages_requested))
		
		# Check if hugetlbfs has been mounted
		if not file_contains_pattern('/proc/mounts', 'hugetlbfs'):
			system('mount -t hugetlbfs none %s' % dir)
		
		os.chdir(self.srcdir)

		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			os.chdir(self.srcdir)
		system('make check')
		if profilers.present():
			profilers.stop(self)
			profilers.report(self)

		system('umount %s' % dir)
