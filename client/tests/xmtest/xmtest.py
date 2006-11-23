# (C) Copyright IBM Corp. 2006
# Author: Paul Larson <pl@us.ibm.com>
# Description:
#	Autotest script for running Xen xm-test
#	This should be run from a Xen domain0

import test
from autotest_utils import *

class xmtest(test.test):
	version = 1

	# This test expects just the xm-test directory, as a tarball
	# from the Xen source tree
	# hg clone http://xenbits.xensource.com/xen-unstable.hg
	# or wget http://www.cl.cam.ac.uk/Research/SRG/netos/xen/downloads/xen-unstable-src.tgz
	# cd tools
	# tar -czf xm-test.tgz xm-test
	def setup(self, tarball = 'xm-test.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./autogen')
		system('./configure')
		system('make existing')

	def execute(self, args = ''):
		os.chdir(self.srcdir)
		system('./runtest.sh ' + args)
		system('mv xmtest.* ' + self.resultsdir)
