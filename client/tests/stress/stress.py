import os
from autotest_lib.client.bin import test, utils


class stress(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # http://weather.ou.edu/~apw/projects/stress/stress-1.0.0.tar.gz
    def setup(self, tarball = 'stress-1.0.0.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def run_once(self, args = ''):
        if not args:
            threads = 2*utils.count_cpus()
            args = '-c %d -i %d -m %d -d %d -t 60 -v' % \
                    (threads, threads, threads, threads)

        utils.system(self.srcdir + '/src/stress ' + args)

# -v                    Turn up verbosity.
# -q                    Turn down verbosity.
# -n                    Show what would have been done (dry-run)
# -t secs               Time out after secs seconds.
# --backoff usecs       Wait for factor of usecs microseconds before starting
# -c forks              Spawn forks processes each spinning on sqrt().
# -i forks              Spawn forks processes each spinning on sync().
# -m forks              Spawn forks processes each spinning on malloc().
# --vm-bytes bytes      Allocate bytes number of bytes. The default is 1.
# --vm-hang             Instruct each vm hog process to go to sleep after
#                       allocating memory. This contrasts with their normal
#                       behavior, which is to free the memory and reallocate
#                       ad infinitum. This is useful for simulating low memory
#                       conditions on a machine. For example, the following
#                       command allocates 256M of RAM and holds it until killed.
#
#                               % stress --vm 2 --vm-bytes 128M --vm-hang
# -d forks              Spawn forks processes each spinning on write().
# --hdd-bytes bytes     Write bytes number of bytes. The default is 1GB.
# --hdd-noclean         Do not unlink file(s) to which random data is written.
#
# Note: Suffixes may be s,m,h,d,y (time) or k,m,g (size).
