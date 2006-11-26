import test
from autotest_utils import *

class stress(test.test):
	version = 1

	# http://weather.ou.edu/~apw/projects/stress/stress-0.18.8.tar.gz
	def setup(self, tarball = 'stress-0.18.8.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')


	def execute(self, iterations = 1, args = ''):
		if not args:
			threads = 2*count_cpus()
			args = '-c %d -i %d -m %d -d %d -t 60 -v' % \
				(threads, threads, threads, threads)

		for i in range(iterations):
			system(self.srcdir + '/src/stress ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/src/stress ' + args)
			profilers.stop(self)
			profilers.report(self)

# -v			Turn up verbosity.
# -q			Turn down verbosity.
# -n			Show what would have been done (dry-run)
# -t secs		Time out after secs seconds. 
# --backoff usecs	Wait for factor of usecs microseconds before starting
# -c forks		Spawn forks processes each spinning on sqrt().
# -i forks		Spawn forks processes each spinning on sync().
# -m forks		Spawn forks processes each spinning on malloc(). 
# --vm-bytes bytes	Allocate bytes number of bytes. The default is 1. 
# --vm-hang		Instruct each vm hog process to go to sleep after 
#			allocating memory. This contrasts with their normal 
#			behavior, which is to free the memory and reallocate 
#			ad infinitum. This is useful for simulating low memory
#			conditions on a machine. For example, the following
#			command allocates 256M of RAM and holds it until killed.
#
#				% stress --vm 2 --vm-bytes 128M --vm-hang
# -d forks		Spawn forks processes each spinning on write(). 
# --hdd-bytes bytes	Write bytes number of bytes. The default is 1GB. 
# --hdd-noclean		Do not unlink file(s) to which random data is written. 
#
# Note: Suffixes may be s,m,h,d,y (time) or k,m,g (size). 

