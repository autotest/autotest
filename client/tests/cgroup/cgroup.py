#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Autotest test for testing cgroup functionalities

@copyright: 2011 Red Hat Inc.
@author: Lukas Doktor <ldoktor@redhat.com>
"""
import os, sys, logging
import time
from tempfile import NamedTemporaryFile

from autotest.client import test, utils
from autotest.client.common_lib import error
from cgroup_common import Cgroup, CgroupModules, get_load_per_cpu

class cgroup(test.test):
    """
    Tests the cgroup functionalities. It works by creating a process (which is
    also a python application) that will try to use CPU and memory. We will
    then verify whether the cgroups rules are obeyed.
    """
    version = 1
    _client = ""
    modules = None

    def run_once(self):
        """
            Try to access different resources which are restricted by cgroup.
        """
        logging.info('Starting cgroup testing')

        err = ""
        # Run available tests
        for subtest in ['memory', 'cpuset']:
            logging.info("---< 'test_%s' START >---", subtest)
            try:
                if not self.modules.get_pwd(subtest):
                    raise error.TestFail("module not available/mounted")
                t_function = getattr(self, "test_%s" % subtest)
                t_function()
                logging.info("---< 'test_%s' PASSED >---", subtest)
            except AttributeError:
                err += "%s, " % subtest
                logging.error("test_%s: Test doesn't exist", subtest)
                logging.info("---< 'test_%s' FAILED >---", subtest)
            except Exception:
                err += "%s, " % subtest
                tb = utils.etraceback("test_%s" % subtest, sys.exc_info())
                logging.error("test_%s: FAILED%s", subtest, tb)
                logging.info("---< 'test_%s' FAILED >---", subtest)

        if err:
            logging.error('Some subtests failed (%s)', err[:-2])
            raise error.TestFail('Some subtests failed (%s)' % err[:-2])


    def setup(self):
        """
        Setup
        """
        logging.debug('Setting up cgroups modules')

        self._client = os.path.join(self.bindir, "cgroup_client.py")

        _modules = ['cpuset', 'ns', 'cpu', 'cpuacct', 'memory', 'devices',
                    'freezer', 'net_cls', 'blkio']
        self.modules = CgroupModules()
        if (self.modules.init(_modules) <= 0):
            raise error.TestFail('Can\'t mount any cgroup modules')


    def cleanup(self):
        """ Cleanup """
        logging.debug('cgroup_test cleanup')
        del (self.modules)


    #############################
    # TESTS
    #############################
    def test_memory(self):
        """
        Memory test
        """
        def cleanup(supress=False):
            """ cleanup """
            logging.debug("test_memory: Cleanup")
            err = ""
            if item.rm_cgroup(pwd):
                err += "\nCan't remove cgroup directory"

            utils.system("swapon -a")

            if err:
                if supress:
                    logging.warn("Some parts of cleanup failed%s", err)
                else:
                    raise error.TestFail("Some parts of cleanup failed%s" % err)

        # Preparation
        item = Cgroup('memory', self._client)
        item.initialize(self.modules)
        item.smoke_test()
        pwd = item.mk_cgroup()

        logging.debug("test_memory: Memory filling test")
        meminfo = open('/proc/meminfo','r')
        mem = meminfo.readline()
        while not mem.startswith("MemFree"):
            mem = meminfo.readline()
        # Use only 1G or max of the free memory
        mem = min(int(mem.split()[1])/1024, 1024)
        mem = max(mem, 100) # at least 100M
        try:
            item.get_property("memory.memsw.limit_in_bytes")
        except error.TestError:
            # Doesn't support memsw limitation -> disabling
            logging.info("System does not support 'memsw'")
            utils.system("swapoff -a")
            memsw = False
        else:
            # Supports memsw
            memsw = True
            # Clear swap
            utils.system("swapoff -a")
            utils.system("swapon -a")
            meminfo.seek(0)
            swap = meminfo.readline()
            while not swap.startswith("SwapTotal"):
                swap = meminfo.readline()
            swap = int(swap.split()[1])/1024
            if swap < mem / 2:
                logging.error("Not enough swap memory to test 'memsw'")
                memsw = False
        meminfo.close()
        outf = NamedTemporaryFile('w+', prefix="cgroup_client-",
                                  dir="/tmp")
        logging.debug("test_memory: Initializition passed")

        ################################################
        # Fill the memory without cgroup limitation
        # Should pass
        ################################################
        logging.debug("test_memory: Memfill WO cgroup")
        ps = item.test("memfill %d %s" % (mem, outf.name))
        ps.stdin.write('\n')
        i = 0
        while ps.poll() == None:
            if i > 60:
                break
            i += 1
            time.sleep(1)
        if i > 60:
            ps.terminate()
            raise error.TestFail("Memory filling failed (WO cgroup)")
        outf.seek(0)
        outf.flush()
        out = outf.readlines()
        if (len(out) < 2) or (ps.poll() != 0):
            raise error.TestFail("Process failed (WO cgroup); output:\n%s"
                                 "\nReturn: %d" % (out, ps.poll()))
        if not out[-1].startswith("PASS"):
            raise error.TestFail("Unsuccessful memory filling "
                                 "(WO cgroup)")
        logging.debug("test_memory: Memfill WO cgroup passed")

        ################################################
        # Fill the memory with 1/2 memory limit
        # memsw: should swap out part of the process and pass
        # WO memsw: should fail (SIGKILL)
        ################################################
        logging.debug("test_memory: Memfill mem only limit")
        ps = item.test("memfill %d %s" % (mem, outf.name))
        item.set_cgroup(ps.pid, pwd)
        item.set_property_h("memory.limit_in_bytes", ("%dM" % (mem/2)), pwd)
        ps.stdin.write('\n')
        i = 0
        while ps.poll() == None:
            if i > 120:
                break
            i += 1
            time.sleep(1)
        if i > 120:
            ps.terminate()
            raise error.TestFail("Memory filling failed (mem)")
        outf.seek(0)
        outf.flush()
        out = outf.readlines()
        if (len(out) < 2):
            raise error.TestFail("Process failed (mem); output:\n%s"
                          "\nReturn: %d" % (out, ps.poll()))
        if memsw:
            if not out[-1].startswith("PASS"):
                logging.error("test_memory: cgroup_client.py returned %d; "
                              "output:\n%s", ps.poll(), out)
                raise error.TestFail("Unsuccessful memory filling (mem)")
        else:
            if out[-1].startswith("PASS"):
                raise error.TestFail("Unexpected memory filling (mem)")
            else:
                filled = int(out[-2].split()[1][:-1])
                if mem/2 > 1.5 * filled:
                    logging.error("test_memory: Limit = %dM, Filled = %dM (+ "
                                  "python overhead upto 1/3 (mem))", mem/2,
                                  filled)
                else:
                    logging.debug("test_memory: Limit = %dM, Filled = %dM (+ "
                                  "python overhead upto 1/3 (mem))", mem/2,
                                  filled)
        logging.debug("test_memory: Memfill mem only cgroup passed")

        ################################################
        # Fill the memory with 1/2 memory+swap limit
        # Should fail
        # (memory.limit_in_bytes have to be set prior to this test)
        ################################################
        if memsw:
            logging.debug("test_memory: Memfill mem + swap limit")
            ps = item.test("memfill %d %s" % (mem, outf.name))
            item.set_cgroup(ps.pid, pwd)
            item.set_property_h("memory.memsw.limit_in_bytes", "%dM"%(mem/2),
                                pwd)
            ps.stdin.write('\n')
            i = 0
            while ps.poll() == None:
                if i > 120:
                    break
                i += 1
                time.sleep(1)
            if i > 120:
                ps.terminate()
                raise error.TestFail("Memory filling failed (mem)")
            outf.seek(0)
            outf.flush()
            out = outf.readlines()
            if (len(out) < 2):
                raise error.TestFail("Process failed (memsw); output:\n%s"
                                     "\nReturn: %d" % (out, ps.poll()))
            if out[-1].startswith("PASS"):
                raise error.TestFail("Unexpected memory filling (memsw)",
                              mem)
            else:
                filled = int(out[-2].split()[1][:-1])
                if mem / 2 > 1.5 * filled:
                    logging.error("test_memory: Limit = %dM, Filled = %dM (+ "
                                  "python overhead upto 1/3 (memsw))", mem/2,
                                  filled)
                else:
                    logging.debug("test_memory: Limit = %dM, Filled = %dM (+ "
                                  "python overhead upto 1/3 (memsw))", mem/2,
                                  filled)
            logging.debug("test_memory: Memfill mem + swap cgroup passed")

        ################################################
        # CLEANUP
        ################################################
        cleanup()



    def test_cpuset(self):
        """
        Cpuset test
        1) Initiate CPU load on CPU0, than spread into CPU* - CPU0
        """
        def cleanup(supress=False):
            """ cleanup """
            logging.debug("test_cpuset: Cleanup")
            err = ""
            try:
                for task in tasks:
                    i = 0
                    for i in range(10):
                        task.terminate()
                        if task.poll() != None:
                            break
                        time.sleep(1)
                    if i >= 9:
                        logging.error("test_cpuset: Subprocess didn't finish")
            except Exception, inst:
                err += "\nCan't terminate tasks: %s" % inst
            if item.rm_cgroup(pwd):
                err += "\nCan't remove cgroup direcotry"
            if err:
                if supress:
                    logging.warn("Some parts of cleanup failed%s", err)
                else:
                    raise error.TestFail("Some parts of cleanup failed%s" % err)

        # Preparation
        item = Cgroup('cpuset', self._client)
        if item.initialize(self.modules):
            raise error.TestFail("cgroup init failed")

        # in cpuset cgroup it's necessarily to set certain values before
        # usage. Thus smoke_test will fail.
        #if item.smoke_test():
        #    raise error.TestFail("smoke_test failed")

        try:
            # Available cpus: cpuset.cpus = "0-$CPUS\n"
            no_cpus = int(item.get_property("cpuset.cpus")[0].split('-')[1]) + 1
        except Exception:
            raise error.TestFail("Failed to get no_cpus or no_cpus = 1")

        pwd = item.mk_cgroup()
        try:
            tmp = item.get_property("cpuset.cpus")[0]
            item.set_property("cpuset.cpus", tmp, pwd)
            tmp = item.get_property("cpuset.mems")[0]
            item.set_property("cpuset.mems", tmp, pwd)
        except Exception:
            cleanup(True)
            raise error.TestFail("Failed to set cpus and mems of"
                                 "a new cgroup")

        ################################################
        # Cpu allocation test
        # Use cpu0 and verify, than all cpu* - cpu0 and verify
        ################################################
        logging.debug("test_cpuset: Cpu allocation test")

        tasks = []
        # Run no_cpus + 1 jobs
        for i in range(no_cpus + 1):
            tasks.append(item.test("cpu"))
            try:
                item.set_cgroup(tasks[i].pid, pwd)
            except error.TestError, inst:
                cleanup(True)
                raise error.TestFail("Failed to set cgroup: %s" % inst)
            tasks[i].stdin.write('\n')
        # Use only the first CPU
        item.set_property("cpuset.cpus", 0, pwd)
        stats = get_load_per_cpu()
        time.sleep(10)
        # [0] = all cpus
        stat1 = get_load_per_cpu(stats)[1:]
        stat2 = stat1[1:]
        stat1 = stat1[0]
        for _stat in stat2:
            if stat1 < _stat:
                cleanup(True)
                raise error.TestFail("Unused processor had higher utilization\n"
                                     "used cpu: %s, remaining cpus: %s"
                                     % (stat1, stat2))

        if no_cpus == 2:
            item.set_property("cpuset.cpus", "1", pwd)
        else:
            item.set_property("cpuset.cpus", "1-%d"%(no_cpus-1), pwd)
        stats = get_load_per_cpu()
        time.sleep(10)
        stat1 = get_load_per_cpu(stats)[1:]
        stat2 = stat1[0]
        stat1 = stat1[1:]
        for _stat in stat1:
            if stat2 > _stat:
                cleanup(True)
                raise error.TestFail("Unused processor had higher utilization\n"
                                     "used cpus: %s, remaining cpu: %s"
                                     % (stat1, stat2))
        logging.debug("test_cpuset: Cpu allocation test passed")

        ################################################
        # CLEANUP
        ################################################
        cleanup()
