"""
cgroup autotest test (on KVM guest)
@author: Lukas Doktor <ldoktor@redhat.com>
@copyright: 2011 Red Hat, Inc.
"""
import logging, re, sys, tempfile, time, traceback
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from client.virt import virt_vm
from autotest_lib.client.tests.cgroup.cgroup_common import Cgroup, CgroupModules

def run_cgroup(test, params, env):
    """
    Tests the cgroup functions on KVM guests.
     * Uses variable tests (marked by TODO comment) to map the subtests
    """
    vms = None
    tests = None

    # Tests
    class _TestBlkioBandwidth:
        """
        BlkioBandwidth dummy test
         * Use it as a base class to an actual test!
         * self.dd_cmd and attr '_set_properties' have to be implemented
         * It prepares 2 vms and run self.dd_cmd to simultaneously stress the
            machines. After 1 minute it kills the dd and gathers the throughput
            information.
        """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            self.vms = vms      # Virt machines
            self.modules = modules          # cgroup module handler
            self.blkio = Cgroup('blkio', '')    # cgroup blkio handler
            self.files = []     # Temporary files (files of virt disks)
            self.devices = []   # Temporary virt devices (PCI drive 1 per vm)
            self.dd_cmd = None  # DD command used to test the throughput

        def cleanup(self):
            """
            Cleanup
            """
            err = ""
            try:
                for i in range (2):
                    vms[i].monitor.cmd("pci_del %s" % self.devices[i])
                    self.files[i].close()
            except Exception, failure_detail:
                err += "\nCan't remove PCI drive: %s" % failure_detail
            try:
                del(self.blkio)
            except Exception, failure_detail:
                err += "\nCan't remove Cgroup: %s" % failure_detail

            if err:
                logging.error("Some cleanup operations failed: %s", err)
                raise error.TestError("Some cleanup operations failed: %s"
                                      % err)

        def init(self):
            """
            Initialization
             * assigns vm1 and vm2 into cgroups and sets the properties
             * creates a new virtio device and adds it into vms
            """
            if test.tagged_testname.find('virtio_blk') == -1:
                logging.warn("The main disk for this VM is non-virtio, keep in "
                             "mind that this particular subtest will add a new "
                             "virtio_blk disk to it")
            if self.dd_cmd is None:
                raise error.TestError("Corrupt class, aren't you trying to run "
                                      "parent _TestBlkioBandwidth() function?")
            if len(self.vms) < 2:
                raise error.TestError("Test needs at least 2 vms.")

            # cgroups
            pwd = []
            blkio = self.blkio
            if blkio.initialize(self.modules):
                raise error.TestError("Could not initialize blkio Cgroup")
            for i in range(2):
                pwd.append(blkio.mk_cgroup())
                if pwd[i] == None:
                    raise error.TestError("Can't create cgroup")
                if blkio.set_cgroup(self.vms[i].get_shell_pid(), pwd[i]):
                    raise error.TestError("Could not set cgroup")
                # Move all existing threads into cgroup
                for tmp in utils.system_output("ps -L --ppid=%d -o lwp"
                                % self.vms[i].get_shell_pid()).split('\n')[1:]:
                    if blkio.set_cgroup(int(tmp), pwd[i]):
                        raise error.TestError("Could not set cgroup")
            if self.blkio.set_property("blkio.weight", 100, pwd[0]):
                raise error.TestError("Could not set blkio.weight")
            if self.blkio.set_property("blkio.weight", 1000, pwd[1]):
                raise error.TestError("Could not set blkio.weight")

            # Add dummy drives
            # TODO: implement also using QMP.
            for i in range(2):
                self.files.append(tempfile.NamedTemporaryFile(
                                        prefix="cgroup-disk-",
                                        suffix=".iso"))
                utils.system("dd if=/dev/zero of=%s bs=1M count=10 &>/dev/null"
                             % (self.files[i].name))
                out = vms[i].monitor.cmd("pci_add auto storage file=%s,"
                                "if=virtio,snapshot=off,cache=off"
                                % (self.files[i].name))
                out = re.search(r'OK domain (\d+), bus (\d+), slot (\d+), '
                                 'function \d+', out).groups()
                self.devices.append("%s:%s:%s" % out)


        def run(self):
            """
            Actual test:
             * executes self.dd_cmd in a loop simultaneously on both vms and
               gather the throughputs. After 1m finish and calculate the avg.
            """
            sessions = []
            out = []
            sessions.append(vms[0].wait_for_login(timeout=30))
            sessions.append(vms[1].wait_for_login(timeout=30))
            sessions.append(vms[0].wait_for_login(timeout=30))
            sessions.append(vms[1].wait_for_login(timeout=30))
            sessions[0].sendline(self.dd_cmd)
            sessions[1].sendline(self.dd_cmd)
            time.sleep(60)

            # Stop the dd loop and kill all remaining dds
            cmd = "rm -f /tmp/cgroup_lock; killall -9 dd"
            sessions[2].sendline(cmd)
            sessions[3].sendline(cmd)
            re_dd = (r'(\d+) bytes \(\d+\.*\d* \w*\) copied, (\d+\.*\d*) s, '
                      '\d+\.*\d* \w./s')
            out = []
            for i in range(2):
                out.append(sessions[i].read_up_to_prompt())
                out[i] = [int(_[0])/float(_[1])
                            for _ in re.findall(re_dd, out[i])[1:-1]]
                logging.debug("dd(%d) output: %s", i, out[i])
                out[i] = [min(out[i]), sum(out[i])/len(out[i]), max(out[i]),
                          len(out[i])]

            for session in sessions:
                session.close()

            logging.debug("dd values (min, avg, max, ddloops):\nout1: %s\nout2:"
                          " %s", out[0], out[1])

            out1 = out[0][1]
            out2 = out[1][1]
            # Cgroup are limitting weights of guests 100:1000. On bare mettal it
            # works in virtio_blk we are satisfied with the ratio 1:3.
            if out1*3  > out2:
                raise error.TestFail("dd values: %s:%s (1:%f), limit 1:2.5"
                                     ", theoretical: 1:10"
                                     % (out1, out2, out2/out1))
            else:
                logging.info("dd values: %s:%s (1:%s)", out1, out2, out2/out1)
            return "dd values: %s:%s (1:%s)" % (out1, out2, out2/out1)



    class TestBlkioBandwidthWeigthRead(_TestBlkioBandwidth):
        """
        Tests the blkio.weight capability using simultaneous read on 2 vms
        """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            _TestBlkioBandwidth.__init__(self, vms, modules)
            # Read from the last vd* in a loop until test removes the
            # /tmp/cgroup_lock file (and kills us)
            self.dd_cmd = ("export FILE=$(ls /dev/vd* | tail -n 1); touch "
                           "/tmp/cgroup_lock ; while [ -e /tmp/cgroup_lock ];"
                           "do dd if=$FILE of=/dev/null iflag=direct bs=100K;"
                           "done")


    class TestBlkioBandwidthWeigthWrite(_TestBlkioBandwidth):
        """
        Tests the blkio.weight capability using simultaneous write on 2 vms
        """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            # Write on the last vd* in a loop until test removes the
            # /tmp/cgroup_lock file (and kills us)
            _TestBlkioBandwidth.__init__(self, vms, modules)
            self.dd_cmd = ('export FILE=$(ls /dev/vd* | tail -n 1); touch '
                           '/tmp/cgroup_lock ; while [ -e /tmp/cgroup_lock ];'
                           'do dd if=/dev/zero of=$FILE oflag=direct bs=100K;'
                           'done')


    def _check_vms(vms):
        """
        Checks if the VM is alive.
        @param vms: list of vm's
        """
        for i in range(len(vms)):
            vms[i].verify_alive()
            try:
                vms[i].verify_kernel_crash()
            except virt_vm.VMDeadKernelCrashError, failure_detail:
                logging.error("_check_vms: %s", failure_detail)
                logging.warn("recreate VM(%s)", i)
                # The vm has to be recreated to reset the qemu PCI state
                vms[i].create()

    def _traceback(name, exc_info):
        """
        Formats traceback into lines "name: line\nname: line"
        @param name: desired line preposition
        @param exc_info: sys.exc_info of the exception
        @return: string which contains beautifully formatted exception
        """
        out = "\n"
        for line in traceback.format_exception(exc_info[0], exc_info[1],
                                               exc_info[2]):
            out += "%s: %s" % (name, line)
        return out


    # Setup
    # TODO: Add all new tests here
    tests = {"blkio_bandwidth_weigth_read"  : TestBlkioBandwidthWeigthRead,
             "blkio_bandwidth_weigth_write" : TestBlkioBandwidthWeigthWrite,
            }
    modules = CgroupModules()
    if (modules.init(['blkio']) <= 0):
        raise error.TestFail('Can\'t mount any cgroup modules')
    # Add all vms
    vms = []
    for vm in params.get("vms", "main_vm").split():
        vm = env.get_vm(vm)
        vm.verify_alive()
        timeout = int(params.get("login_timeout", 360))
        _ = vm.wait_for_login(timeout=timeout)
        _.close()
        del(_)
        vms.append(vm)


    # Execute tests
    results = ""
    # cgroup_tests = "re1[:loops] re2[:loops] ... ... ..."
    for rexpr in params.get("cgroup_tests").split():
        try:
            loops = int(rexpr[rexpr.rfind(':')+1:])
            rexpr = rexpr[:rexpr.rfind(':')]
        except Exception:
            loops = 1
        # number of loops per regular expression
        for _loop in range(loops):
            # cg_test is the subtest name from regular expression
            for cg_test in [_ for _ in tests.keys() if re.match(rexpr, _)]:
                logging.info("%s: Entering the test", cg_test)
                try:
                    _check_vms(vms)
                    tst = tests[cg_test](vms, modules)
                    tst.init()
                    out = tst.run()
                except error.TestFail, failure_detail:
                    logging.error("%s: Leaving, test FAILED (TestFail): %s",
                                  cg_test, failure_detail)
                    results += "\n * %s: Test FAILED (TestFail): %s" % (cg_test,
                                                                failure_detail)
                    try:
                        tst.cleanup()
                    except Exception, failure_detail:
                        tb = _traceback("%s cleanup:" % cg_test, sys.exc_info())
                        logging.info("%s: cleanup also failed\n%s", cg_test, tb)
                except error.TestError, failure_detail:
                    tb = _traceback(cg_test, sys.exc_info())
                    logging.error("%s: Leaving, test FAILED (TestError): %s",
                                  cg_test, tb)
                    results += "\n * %s: Test FAILED (TestError): %s"% (cg_test,
                                                                failure_detail)
                    try:
                        tst.cleanup()
                    except Exception, failure_detail:
                        logging.warn("%s: cleanup also failed: %s\n", cg_test,
                                                                failure_detail)
                except Exception, failure_detail:
                    tb = _traceback(cg_test, sys.exc_info())
                    logging.error("%s: Leaving, test FAILED (Exception): %s",
                                  cg_test, tb)
                    results += "\n * %s: Test FAILED (Exception): %s"% (cg_test,
                                                                failure_detail)
                    try:
                        tst.cleanup()
                    except Exception, failure_detail:
                        logging.warn("%s: cleanup also failed: %s\n", cg_test,
                                                                failure_detail)
                else:
                    try:
                        tst.cleanup()
                    except Exception, failure_detail:
                        tb = _traceback("%s cleanup:" % cg_test, sys.exc_info())
                        logging.info("%s: Leaving, test passed but cleanup "
                                     "FAILED\n%s", cg_test, tb)
                        results += ("\n * %s: Test passed but cleanup FAILED"
                                    % (cg_test))
                    else:
                        logging.info("%s: Leaving, test PASSED", cg_test)
                        results += "\n * %s: Test PASSED: %s" % (cg_test, out)

    out = ("SUM: All tests finished (%d PASS / %d FAIL = %d TOTAL)%s" %
           (results.count("PASSED"), results.count("FAILED"),
            (results.count("PASSED")+results.count("FAILED")), results))
    logging.info(out)
    if results.count("FAILED"):
        raise error.TestFail("Some subtests failed\n%s" % out)

