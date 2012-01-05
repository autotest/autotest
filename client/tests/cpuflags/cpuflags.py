#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Autotest test for testing main group ofcpu flags functionalitines.

@copyright: 2011 Red Hat Inc.
@author: Jiří Župka <jzupka@redhat.com>
"""
import os, logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils

class cpuflags(test.test):
    """
    Tests the cpuflags functionalities.
    """
    version = 1

    def setup(self, tarball = 'cpuflags_test.tar.bz2'):
        def install_cpuflags_test(tarball):
            """
            Compile stress test.

            @param vm: virtual machine.
            @param dst_dir: Installation path.
            """
            scriptdir = os.path.join(self.job.autodir, "virt", "scripts",
                                     "cpuflags-test")
            scriptdir_src = os.path.join(scriptdir, "src")
            os.mkdir(self.srcdir)
            os.chdir(self.srcdir)
            utils.system('cp %s %s' % (os.path.join(scriptdir_src, "*"),
                         self.srcdir))
            utils.make()
            utils.system('sync')

        self.job.require_gcc()
        install_cpuflags_test(tarball)


    def run_once(self):
        """
            Try to access different resources which are restricted by cgroup.
        """
        logging.info('Starting cpuflags testing')
        def check_cpuflags_work(flags):
            """
            Check which flags work.

            @param vm: Virtual machine.
            @param path: Path of cpuflags_test
            @param flags: Flags to test.
            @return: Tuple (Working, not working, not tested) flags.
            """
            pass_Flags = []
            not_tested = []
            not_working = []
            for f in flags:
                try:
                    for tc in virt_utils.kvm_map_flags_to_test[f]:
                        utils.run("./cpuflags-test --%s" % (tc))
                    pass_Flags.append(f)
                except error.CmdError:
                    not_working.append(f)
                except KeyError:
                    not_tested.append(f)
            return (pass_Flags, not_working, not_tested)


        def run_stress(timeout, flags, smp):
            """
            Run stress on vm for timeout time.
            """
            ret = False
            flags = check_cpuflags_work(flags)
            try:
                utils.run("./cpuflags-test --stress %s%s" %
                          (smp, virt_utils.kvm_flags_to_stresstests(flags[0])),
                          timeout)
            except error.CmdError:
                ret = True
            return ret


        os.chdir(self.srcdir)
        run_stress(60, set(map(virt_utils.Flag, virt_utils.get_cpu_flags())), 4)


    def cleanup(self):
        """ Cleanup """
        logging.debug('cpuflags_test cleanup')
