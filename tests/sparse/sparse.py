import test
from autotest_utils import *

# THIS TEST IS INCOMPLETE. IT WILL NOT WORK

class sparse(test.test):
	version = 1

	# http://www.codemonkey.org.uk/projects/git-snapshots/sparse/sparse-2006-04-28.tar.gz
	def setup(self, tarball = 'sparse-2006-04-28.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		system('ln check sparse')
	
		self.top_dir = self.job.tmpdir+'/sparse'	
		
	def execute(self, kernel):
		kernel.build(make_opts = 'C=1')
