import time, os, logging, re, sys
from autotest.client import test, utils, os_dep
from autotest.client.common_lib import error

class cpu_hotplug(test.test):
    version = 2

    # http://developer.osdl.org/dev/hotplug/tests/lhcs_regression-1.6.tgz
    def setup(self, tarball = 'lhcs_regression-1.6.tgz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.run("patch -p1 < ../0001-LHCS-Cleanups-and-bugfixes.patch")


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
        tests_fail = []
        tests_pass = []
        # Begin this cpu hotplug test big guru.
        os.chdir(self.srcdir)
        result_cmd = utils.run('./runtests.sh', stdout_tee=sys.stdout)
        for line in result_cmd.stdout.splitlines():
            match = re.findall('^([\w:\.]+)\s+([A-Z]+):(.*)$', line)
            if match:
                info = {}
                info['testname'] = match[0][0]
                info['status'] = match[0][1]
                info['reason'] = match[0][2]
                if info['status'] == 'FAIL':
                    logging.info("%s: %s -> %s",
                                 info['testname'], info['status'],
                                 info['reason'])
                    tests_fail.append(info)
                elif info['status'] == 'PASS':
                    logging.info("%s: %s -> %s",
                                 info['testname'], info['status'],
                                 info['reason'])
                    tests_pass.append(info)

        if tests_fail:
            raise error.TestFail("%d from %d tests FAIL" %
                                 (len(tests_fail),
                                  len(tests_pass) + len(tests_fail)))
        else:
            logging.info("All %d tests PASS" % len(tests_pass))
