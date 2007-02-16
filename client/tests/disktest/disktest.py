import test
from autotest_utils import *
import os, sys
from subprocess import *

class disktest(test.test):
	version = 1

	def setup(self):
		os.mkdir(self.srcdir)
		os.chdir(self.bindir)
		system('cp disktest.c src/')
		os.chdir(self.srcdir)
		cflags = '-D_FILE_OFFSET_BITS=64 -D _GNU_SOURCE -static -Wall'
		system('cc disktest.c ' + cflags + ' -o disktest')


	def test_one_disk_chunk(self, disk, chunk):
		print "testing %d MB files on %s in %d MB memory" % \
					(self.chunk_mb, disk, self.memory_mb)
		cmd = "%s/disktest -m %d -f %s/testfile.%d -i -S" % \
				(self.srcdir, self.chunk_mb, disk, chunk)
		p = Popen(cmd, shell=True)
		return(p.pid)


	def execute(self, disks, gigabytes = 100, chunk_mb = memtotal()/1024):
		os.chdir(self.srcdir)

		self.chunk_mb = chunk_mb
		self.memory_mb = memtotal()/1024
		if self.memory_mb > chunk_mb:
			raise "Too much RAM (%dMB) for this test to work" % \
								self.memory_mb

		chunks = (1024 * gigabytes) / chunk_mb

		for i in range(chunks):
			pids = []
			for disk in disks:
				pid = self.test_one_disk_chunk(disk, i)
				pids.append(pid)
			errors = []
			for pid in pids:
				(junk, retval) = os.waitpid(pid, 0)
				if (retval != 0):
					errors.append(retval)
			if errors:
				raise "Errors from children: %s" % errors
		
