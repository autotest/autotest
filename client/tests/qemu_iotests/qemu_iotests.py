import os, re, logging
from autotest_lib.client.bin import test, utils, os_dep
from autotest_lib.client.common_lib import error


class qemu_iotests(test.test):
    """
    This autotest module runs the qemu_iotests testsuite.

    @copyright: Red Hat 2009
    @author: Yolkfull Chow (yzhou@redhat.com)
    @see: http://www.kernel.org/pub/scm/linux/kernel/git/hch/qemu-iotests.git
    """
    version = 2
    def initialize(self, qemu_path=''):
        if qemu_path:
            # Prepending the path at the beginning of $PATH will make the
            # version found on qemu_path be preferred over other ones.
            os.environ['PATH'] =  qemu_path + ":" + os.environ['PATH']
        try:
            self.qemu_img_path = os_dep.command('qemu-img')
            self.qemu_io_path = os_dep.command('qemu-io')
        except ValueError, e:
            raise error.TestNAError('Commands qemu-img or qemu-io missing')
        self.job.require_gcc()


    def setup(self, tarball='qemu-iotests.tar.bz2'):
        """
        Uncompresses the tarball and cleans any leftover output files.

        @param tarball: Relative path to the testsuite tarball.
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.make('clean')


    def run_once(self, options='', testlist=''):
        """
        Passes the appropriate parameters to the testsuite.

        # Usage: $0 [options] [testlist]
        # check options
        #     -raw                test raw (default)
        #     -cow                test cow
        #     -qcow               test qcow
        #     -qcow2              test qcow2
        #     -vpc                test vpc
        #     -vmdk               test vmdk
        #     -xdiff              graphical mode diff
        #     -nocache            use O_DIRECT on backing file
        #     -misalign           misalign memory allocations
        #     -n                  show me, do not run tests
        #     -T                  output timestamps
        #     -r                  randomize test order
        #
        # testlist options
        #     -g group[,group...] include tests from these groups
        #     -x group[,group...] exclude tests from these groups
        #     NNN                 include test NNN
        #     NNN-NNN             include test range (eg. 012-021)

        @param qemu_path: Optional qemu install path.
        @param options: Options accepted by the testsuite.
        @param testlist: List of tests that will be executed (by default, all
                testcases will be executed).
        """
        os.chdir(self.srcdir)
        test_dir = os.path.join(self.srcdir, "scratch")
        if not os.path.exists(test_dir):
            os.mkdir(test_dir)
        cmd = "./check"
        if options:
            cmd += " " + options
        if testlist:
            cmd += " " + testlist

        try:
            try:
                result = utils.system(cmd)
            except error.CmdError, e:
                failed_cases = re.findall("Failures: (\d+)", str(e))
                for num in failed_cases:
                    failed_name = num + ".out.bad"
                    src = os.path.join(self.srcdir, failed_name)
                    dest = os.path.join(self.resultsdir, failed_name)
                    utils.get_file(src, dest)
                if failed_cases:
                    e_msg = ("Qemu-iotests failed. Failed cases: %s" %
                             failed_cases)
                else:
                    e_msg = "Qemu-iotests failed"
                raise error.TestFail(e_msg)
        finally:
            src = os.path.join(self.srcdir, "check.log")
            dest = os.path.join(self.resultsdir, "check.log")
            utils.get_file(src, dest)
