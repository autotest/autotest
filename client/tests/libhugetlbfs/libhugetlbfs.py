import re, os
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

class libhugetlbfs(test.test):
    version = 6

    def initialize(self, dir = None, pages_requested = 20):
        self.dir = None

        self.job.require_gcc()

        utils.check_kernel_ver("2.6.16")

        # Check huge page number
        pages_available = 0
        if os.path.exists('/proc/sys/vm/nr_hugepages'):
            utils.write_one_line('/proc/sys/vm/nr_hugepages',
                                          str(pages_requested))
            nr_hugepages = utils.read_one_line('/proc/sys/vm/nr_hugepages')
            pages_available = int(nr_hugepages)
        else:
            raise error.TestNAError('Kernel does not support hugepages')

        if pages_available < pages_requested:
            raise error.TestError('%d huge pages available, < %d pages requested' % (pages_available, pages_requested))

        # Check if hugetlbfs has been mounted
        if not utils.file_contains_pattern('/proc/mounts', 'hugetlbfs'):
            if not dir:
                dir = os.path.join(self.tmpdir, 'hugetlbfs')
                os.makedirs(dir)
            utils.system('mount -t hugetlbfs none %s' % dir)
            self.dir = dir


    # http://libhugetlbfs.ozlabs.org/releases/libhugetlbfs-2.0.tar.gz
    def setup(self, tarball = 'libhugetlbfs-2.0.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('patch -p1 < ../elflink.patch')
        # make might fail if there are no proper headers for the 32 bit
        # version, in that case try only for the 64 bit version
        try:
            utils.make()
        except:
            utils.make('OBJDIRS=obj64')


    def run_once(self):
        os.chdir(self.srcdir)
        # make check might fail for 32 bit if the 32 bit compile earlier
        # had failed. See if it passes for 64 bit in that case.
        try:
            utils.make('check')
        except:
            utils.make('check OBJDIRS=obj64')


    def cleanup(self):
        if self.dir:
            utils.system('umount %s' % self.dir)
