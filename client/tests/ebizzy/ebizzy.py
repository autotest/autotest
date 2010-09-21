import os
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

class ebizzy(test.test):
    version = 3

    def initialize(self):
        self.job.require_gcc()


    # http://sourceforge.net/project/downloading.php?group_id=202378&filename=ebizzy-0.3.tar.gz
    def setup(self, tarball='ebizzy-0.3.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('[ -x configure ] && ./configure')
        utils.make()


    # Note: default we use always mmap()
    def run_once(self, args='', num_chunks=1000, chunk_size=512000,
                 seconds=100, num_threads=100):

        #TODO: Write small functions which will choose many of the above
        # variables dynamicaly looking at guest's total resources
        logfile = os.path.join(self.resultsdir, 'ebizzy.log')
        args2 = '-m -n %s -P -R -s %s -S %s -t %s' % (num_chunks, chunk_size,
                                                      seconds, num_threads)
        args = args + ' ' + args2
