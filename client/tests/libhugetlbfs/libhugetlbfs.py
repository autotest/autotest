import re, os
from autotest_lib.client.bin import autotest_utils, tests
from autotest_lib.client.common_lib import utils, error

class libhugetlbfs(test.test):
	version = 4

	# http://libhugetlbfs.ozlabs.org/releases/libhugetlbfs-1.3-pre1.tar.gz
	def setup(self, tarball = 'libhugetlbfs-1.3-pre1.tar.gz'):
		tarball = autotest_utils.unmap_url(self.bindir, tarball,
		                                   self.tmpdir)
		autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		# make might fail if there are no proper headers for the 32 bit
		# version, in that case try only for the 64 bit version
		try:
			utils.system('make')
		except:
			utils.system('make OBJDIRS=obj64')

	def execute(self, dir = None, pages_requested = 20):
		autotest_utils.check_kernel_ver("2.6.16")

		# Check huge page number
		pages_available = 0
		if os.path.exists('/proc/sys/vm/nr_hugepages'):
			autotest_utils.write_one_line('/proc/sys/vm/nr_hugepages',
						      str(pages_requested))
			pages_available = int(open('/proc/sys/vm/nr_hugepages', 'r').readline())
		else:
			raise error.TestNAError('Kernel does not support hugepages')

		if pages_available < pages_requested:
			raise error.TestError('%d huge pages available, < %d pages requested' % (pages_available, pages_requested))

		# Check if hugetlbfs has been mounted
		if not autotest_utils.file_contains_pattern('/proc/mounts', 'hugetlbfs'):
			if not dir:
				dir = os.path.join(self.tmpdir, 'hugetlbfs')
				os.makedirs(dir)
			utils.system('mount -t hugetlbfs none %s' % dir)

		os.chdir(self.srcdir)

		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			os.chdir(self.srcdir)
		# make check might fail for 32 bit if the 32 bit compile earlier
		# had failed. See if it passes for 64 bit in that case.
		try:
			utils.system('make check')
		except:
			utils.system('make check OBJDIRS=obj64')
		if profilers.present():
			profilers.stop(self)
			profilers.report(self)

		utils.system('umount %s' % dir)
