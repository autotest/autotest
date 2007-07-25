import test
from autotest_utils import *
import re, time
from subprocess import *

class parallel_dd(test.test):
	version = 1

	def write_out(self):
		p = []
		# Write out 'streams' files in parallel background tasks
		for i in range(self.streams):
			file = 'poo%d' % (i+1)
			file = os.path.join(self.job.tmpdir, file)
			dd = 'dd if=/dev/zero of=%s bs=4K count=%d' % \
						(file, self.blocks_per_file)
			print dd
			p.append(Popen(dd, shell=True))
		print "Waiting for %d streams" % self.streams
		# Wait for everyone to complete
		for i in range(self.streams):
			print "Waiting for %d" % p[i].pid
			sys.stdout.flush()
			sys.stderr.flush()
			os.waitpid(p[i].pid, 0)
		sys.stdout.flush()
		sys.stderr.flush()


	def read_in(self):
		for i in range(self.streams):
			file = os.path.join(self.job.tmpdir, 'poo%d' % (i+1))
			system('cat %s > /dev/null' % file)


	def test(self, tag):
		self.fs.mount()
		t1 = time.time()

		try:
			self.write_out()
		except:
			try:
				self.fs.unmount()
			finally:
				raise
		self.fs.unmount()

		t2 = time.time()

		self.fs.mount()
		try:
			self.read_in()
		except:
			try:
				self.fs.unmount()
			finally:
				raise
			read_in()

		t3 = time.time()
		self.fs.unmount()

		return (t2 - t1, t3 - t2)
		

	def execute(self, fs, fstype = 'ext2', iterations = 2, megabytes = 1000, streams = 2):
		self.blocks_per_file = (megabytes * 256) / streams
		self.fs = fs
		self.streams = streams
		
		print "Dumping %d megabytes across %d streams, %d times" % \
						(megabytes, streams, iterations)
		# fs.mkfs(fstype)

		keyval = open(os.path.join(self.resultsdir, 'keyval'), 'w')
		for i in range(iterations):
			(out_time, in_time) = self.test('%d' % i)
			t = "out=%d\nin=%d\n\n" % (out_time, in_time)
			print t
			keyval.write(t)
		keyval.close()


		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			self.test('profile')
			profilers.stop(self)
			profilers.report(self)
