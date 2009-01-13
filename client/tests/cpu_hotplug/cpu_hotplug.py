import time, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class cpu_hotplug(test.test):
    version = 2

    # http://developer.osdl.org/dev/hotplug/tests/lhcs_regression-1.6.tgz
    def setup(self, tarball = 'lhcs_regression-1.6.tgz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)


    def initialize(self):
        # Check if the kernel supports cpu hotplug
        if utils.running_config():
            utils.check_for_kernel_feature('HOTPLUG_CPU')

        # Check cpu nums, if equals 1, quit.
        if utils.count_cpus() == 1:
            e_msg = 'Single CPU online detected, test not supported.'
            raise error.TestNAError(e_msg)

        # Have a simple and quick check first, FIX me please.
        utils.system('dmesg -c > /dev/null')
        for cpu in utils.cpu_online_map():
            if os.path.isfile('/sys/devices/system/cpu/cpu%s/online' % cpu):
                utils.system('echo 0 > /sys/devices/system/cpu/cpu%s/online' % cpu, 1)
                utils.system('dmesg -c')
                time.sleep(3)
                utils.system('echo 1 > /sys/devices/system/cpu/cpu%s/online' % cpu, 1)
                utils.system('dmesg -c')
                time.sleep(3)


    def run_once(self):
        # Begin this cpu hotplug test big guru.
        os.chdir(self.srcdir)
        utils.system('./runtests.sh')
