import time, os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils

class cpu_hotplug(test.test):
    version = 2

    # http://developer.osdl.org/dev/hotplug/tests/lhcs_regression-1.6.tgz
    def setup(self, tarball = 'lhcs_regression-1.6.tgz'):
        tarball = utils.unmap_url(self.bindir, tarball,
                                           self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)

    def execute(self):
        # Check if the kernel supports cpu hotplug
        if autotest_utils.running_config():
            autotest_utils.check_for_kernel_feature('HOTPLUG_CPU')

        # Check cpu nums, if equals 1, quit.
        if autotest_utils.count_cpus() == 1:
            print 'Just only single cpu online, quiting...'
            sys.exit()

        # Have a simple and quick check first, FIX me please.
        utils.system('dmesg -c > /dev/null')
        for cpu in autotest_utils.cpu_online_map():
            if os.path.isfile('/sys/devices/system/cpu/cpu%s/online' % cpu):
                utils.system('echo 0 > /sys/devices/system/cpu/cpu%s/online' % cpu, 1)
                utils.system('dmesg -c')
                time.sleep(3)
                utils.system('echo 1 > /sys/devices/system/cpu/cpu%s/online' % cpu, 1)
                utils.system('dmesg -c')
                time.sleep(3)

        # Begin this cpu hotplug test big guru.
        os.chdir(self.srcdir)
        profilers = self.job.profilers
        if not profilers.only():
            utils.system('./runtests.sh')

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            utils.system('./runtests.sh')
            profilers.stop(self)
            profilers.report(self)
