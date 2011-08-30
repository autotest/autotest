import os, logging
import time
from tempfile import NamedTemporaryFile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from cgroup_common import Cgroup as CG
from cgroup_common import CgroupModules

class cgroup(test.test):
    """
    Tests the cgroup functionalities. It works by creating a process (which is
    also a python application) that will try to use CPU and memory. We will
    then verify whether the cgroups rules are obeyed.
    """
    version = 1
    _client = ""
    modules = CgroupModules()

    def run_once(self):
        """
	    Try to access different resources which are restricted by cgroup.
        """
        logging.info('Starting cgroup testing')

        err = ""
        # Run available tests
        for i in ['memory', 'cpuset']:
            logging.info("---< 'test_%s' START >---", i)
            try:
                if not self.modules.get_pwd(i):
                    raise error.TestFail("module not available/mounted")
                t_function = getattr(self, "test_%s" % i)
                t_function()
                logging.info("---< 'test_%s' PASSED >---", i)
            except AttributeError:
                err += "%s, " % i
                logging.error("test_%s: Test doesn't exist", i)
                logging.info("---< 'test_%s' FAILED >---", i)
            except Exception, inst:
                err += "%s, " % i
                logging.error("test_%s: %s", i, inst)
                logging.info("---< 'test_%s' FAILED >---", i)

        if err:
            logging.error('Some subtests failed (%s)' % err[:-2])
            raise error.TestFail('Some subtests failed (%s)' % err[:-2])


    def setup(self):
        """
        Setup
        """
        logging.debug('Setting up cgroups modules')

        self._client = os.path.join(self.bindir, "cgroup_client.py")

        _modules = ['cpuset', 'ns', 'cpu', 'cpuacct', 'memory', 'devices',
                    'freezer', 'net_cls', 'blkio']
        if (self.modules.init(_modules) <= 0):
            raise error.TestFail('Can\'t mount any cgroup modules')


    def cleanup(self):
        """
        Unmount all cgroups and remove directories
        """
        logging.info('Cleanup')
        self.modules.cleanup()


    #############################
    # TESTS
    #############################
    def test_memory(self):
        """
        Memory test
        """
        def cleanup(supress=False):
            # cleanup
            logging.debug("test_memory: Cleanup")
            err = ""
            if item.rm_cgroup(pwd):
                err += "\nCan't remove cgroup directory"

            utils.system("swapon -a")

            if err:
                if supress:
                    logging.warn("Some parts of cleanup failed%s" % err)
                else:
                    raise error.TestFail("Some parts of cleanup failed%s" % err)

        # Preparation
        item = CG('memory', self._client)
        if item.initialize(self.modules):
            raise error.TestFail("cgroup init failed")

        if item.smoke_test():
            raise error.TestFail("smoke_test failed")

        pwd = item.mk_cgroup()
        if pwd == None:
            raise error.TestFail("Can't create cgroup")

        logging.debug("test_memory: Memory filling test")

        f = open('/proc/meminfo','r')
        mem = f.readline()
        while not mem.startswith("MemFree"):
            mem = f.readline()
        # Use only 1G or max of the free memory
        mem = min(int(mem.split()[1])/1024, 1024)
        mem = max(mem, 100) # at least 100M
        memsw_limit_bytes = item.get_property("memory.memsw.limit_in_bytes",
                                              supress=True)
        if memsw_limit_bytes is not None:
            memsw = True
            # Clear swap
            utils.system("swapoff -a")
            utils.system("swapon -a")
            f.seek(0)
            swap = f.readline()
            while not swap.startswith("SwapTotal"):
                swap = f.readline()
            swap = int(swap.split()[1])/1024
            if swap < mem / 2:
                logging.error("Not enough swap memory to test 'memsw'")
                memsw = False
        else:
            # Doesn't support swap + memory limitation, disable swap
            logging.info("System does not support 'memsw'")
            utils.system("swapoff -a")
            memsw = False
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
        if item.set_cgroup(ps.pid, pwd):
            raise error.TestFail("Could not set cgroup")
        if item.set_prop("memory.limit_in_bytes", ("%dM" % (mem/2)), pwd):
            raise error.TestFail("Could not set mem limit (mem)")
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
            if item.set_cgroup(ps.pid, pwd):
                raise error.TestFail("Could not set cgroup (memsw)")
            if item.set_prop("memory.memsw.limit_in_bytes", "%dM"%(mem/2), pwd):
                raise error.TestFail("Could not set mem limit (memsw)")
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
        class per_cpu_load:
            """
            Handles the per_cpu_load stats
            self.values [cpus, cpu0, cpu1, ...]
            """
            def __init__(self):
                """
                Init
                """
                self.values = []
                self.f = open('/proc/stat', 'r')
                line = self.f.readline()
                while line:
                    if line.startswith('cpu'):
                        self.values.append(int(line.split()[1]))
                    else:
                        break
                    line = self.f.readline()

            def reload(self):
                """
                Reload current values
                """
                self.values = self.get()

            def get(self):
                """
                Get the current values
                @return vals: array of current values [cpus, cpu0, cpu1..]
                """
                self.f.seek(0)
                self.f.flush()
                vals = []
                for i in range(len(self.values)):
                    vals.append(int(self.f.readline().split()[1]))
                return vals

            def tick(self):
                """
                Reload values and returns the load between the last tick/reload
                @return vals: array of load between ticks/reloads
                              values [cpus, cpu0, cpu1..]
                """
                vals = self.get()
                ret = []
                for i in range(len(self.values)):
                    ret.append(vals[i] - self.values[i])
                self.values = vals
                return ret

        def cleanup(supress=False):
            # cleanup
            logging.debug("test_cpuset: Cleanup")
            err = ""
            try:
                for task in tasks:
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
                    logging.warn("Some parts of cleanup failed%s" % err)
                else:
                    raise error.TestFail("Some parts of cleanup failed%s" % err)

        # Preparation
        item = CG('cpuset', self._client)
        if item.initialize(self.modules):
            raise error.TestFail("cgroup init failed")

        # FIXME: new cpuset cgroup doesn't have any mems and cpus assigned
        # thus smoke_test won't work
        #if item.smoke_test():
        #    raise error.TestFail("smoke_test failed")

        try:
            # Available cpus: cpuset.cpus = "0-$CPUS\n"
            no_cpus = int(item.get_prop("cpuset.cpus").split('-')[1]) + 1
        except:
            raise error.TestFail("Failed to get no_cpus or no_cpus = 1")

        pwd = item.mk_cgroup()
        if pwd == None:
            raise error.TestFail("Can't create cgroup")
        # FIXME: new cpuset cgroup doesn't have any mems and cpus assigned
        try:
            tmp = item.get_prop("cpuset.cpus")
            item.set_property("cpuset.cpus", tmp, pwd)
            tmp = item.get_prop("cpuset.mems")
            item.set_property("cpuset.mems", tmp, pwd)
        except:
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
            if item.set_cgroup(tasks[i].pid, pwd):
                cleanup(True)
                raise error.TestFail("Failed to set cgroup")
            tasks[i].stdin.write('\n')
        stats = per_cpu_load()
        # Use only the first CPU
        item.set_property("cpuset.cpus", 0, pwd)
        stats.reload()
        time.sleep(10)
        # [0] = all cpus
        s1 = stats.tick()[1:]
        s2 = s1[1:]
        s1 = s1[0]
        for _s in s2:
            if s1 < _s:
                cleanup(True)
                raise error.TestFail("Unused processor had higher utilization\n"
                                     "used cpu: %s, remaining cpus: %s"
                                     % (s1, s2))

        if no_cpus == 2:
            item.set_property("cpuset.cpus", "1", pwd)
        else:
            item.set_property("cpuset.cpus", "1-%d"%(no_cpus-1), pwd)
        stats.reload()
        time.sleep(10)
        s1 = stats.tick()[1:]
        s2 = s1[0]
        s1 = s1[1:]
        for _s in s1:
            if s2 > _s:
                cleanup(True)
                raise error.TestFail("Unused processor had higher utilization\n"
                                     "used cpus: %s, remaining cpu: %s"
                                     % (s1, s2))
        logging.debug("test_cpuset: Cpu allocation test passed")

        ################################################
        # CLEANUP
        ################################################
        cleanup()
