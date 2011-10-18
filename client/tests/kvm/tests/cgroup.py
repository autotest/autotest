"""
cgroup autotest test (on KVM guest)
@author: Lukas Doktor <ldoktor@redhat.com>
@copyright: 2011 Red Hat, Inc.
"""
import logging, re, sys, tempfile, time
from random import random
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.tests.cgroup.cgroup_common import Cgroup, CgroupModules

def run_cgroup(test, params, env):
    """
    Tests the cgroup functions on KVM guests.
     * Uses variable tests (marked by TODO comment) to map the subtests
    """
    vms = None
    tests = None


    # Func
    def _check_vms(vms):
        """
        Checks if the VM is alive.
        @param vms: list of vm's
        """
        err = ""
        for i in range(len(vms)):
            try:
                vms[i].verify_alive()
                vms[i].verify_kernel_crash()
                vms[i].wait_for_login(timeout=30).close()
            except Exception, failure_detail:
                logging.error("_check_vms: %s", failure_detail)
                logging.warn("recreate VM(%s)", i)
                # The vm has to be recreated to reset the qemu PCI state
                vms[i].create()
                err += "%s, " % vms[i].name
        if err:
            raise error.TestFail("WM [%s] had to be recreated" % err[:-2])


    def distance(actual, reference):
        """
        Absolute value of relative distance of two numbers
        @param actual: actual value
        @param reference: reference value
        @return: relative distance abs((a-r)/r) (float)
        """
        return abs(float(actual-reference) / reference)


    def get_dd_cmd(direction, dev='vd?', count=None, bs=None):
        """
        Generates dd_cmd string
        @param direction: {read,write,bi} dd direction
        @param dev: used device ('vd?')
        @param count: count parameter of dd
        @param bs: bs parameter of dd
        @return: dd command string
        """
        if direction == "read":
            params = "if=$FILE of=/dev/null iflag=direct"
        elif direction == "write":
            params = "if=/dev/zero of=$FILE oflag=direct"
        else:
            params = "if=$FILE of=$FILE iflag=direct oflag=direct"
        if bs:
            params += " bs=%s" % (bs)
        if count:
            params += " count=%s" % (count)
        return ("export FILE=$(ls /dev/%s | tail -n 1); touch /tmp/cgroup_lock "
                "; while [ -e /tmp/cgroup_lock ]; do dd %s ; done"
                % (dev, params))


    def get_device_driver():
        """
        Discovers the used block device driver {ide, scsi, virtio_blk}
        @return: Used block device driver {ide, scsi, virtio}
        """
        return params.get('drive_format', 'virtio')


    def add_file_drive(vm, driver=get_device_driver(), host_file=None):
        """
        Hot-add a drive based on file to a vm
        @param vm: Desired VM
        @param driver: which driver should be used (default: same as in test)
        @param host_file: Which file on host is the image (default: create new)
        @return: Tupple(ret_file, device)
                    ret_file: created file handler (None if not created)
                    device: PCI id of the virtual disk
        """
        # TODO: Implement also via QMP
        if not host_file:
            host_file = tempfile.NamedTemporaryFile(prefix="cgroup-disk-",
                                               suffix=".iso")
            utils.system("dd if=/dev/zero of=%s bs=1M count=8 &>/dev/null"
                         % (host_file.name))
            ret_file = host_file
            logging.debug("add_file_drive: new file %s as drive", host_file)
        else:
            ret_file = None
            logging.debug("add_file_drive: using file %s as drive", host_file)

        out = vm.monitor.cmd("pci_add auto storage file=%s,if=%s,snapshot=off,"
                             "cache=off" % (host_file.name, driver))
        dev = re.search(r'OK domain (\d+), bus (\d+), slot (\d+), function \d+',
                        out)
        if not dev:
            raise error.TestFail("Can't add device(%s, %s, %s): %s" % (vm.name,
                                                host_file.name, driver, out))
        device = "%02x:%02x" % (int(dev.group(2)), int(dev.group(3)))
        time.sleep(3)
        out = vm.monitor.info('qtree', debug=False)
        if out.count('addr %s.0' % device) != 1:
            raise error.TestFail("Can't add device(%s, %s, %s): device in qtree"
                            ":\n%s" % (vm.name, host_file.name, driver, out))
        return (ret_file, device)


    def add_scsi_drive(vm, driver=get_device_driver(), host_file=None):
        """
        Hot-add a drive based on scsi_debug device to a vm
        @param vm: Desired VM
        @param driver: which driver should be used (default: same as in test)
        @param host_file: Which dev on host is the image (default: create new)
        @return: Tupple(ret_file, device)
                    ret_file: string of the created dev (None if not created)
                    device: PCI id of the virtual disk
        """
        # TODO: Implement also via QMP
        if not host_file:
            if utils.system("lsmod | grep scsi_debug", ignore_status=True):
                utils.system("modprobe scsi_debug dev_size_mb=8 add_host=0")
            utils.system("echo 1 > /sys/bus/pseudo/drivers/scsi_debug/add_host")
            time.sleep(1)   # Wait for device init
            host_file = utils.system_output("ls /dev/sd* | tail -n 1")
            # Enable idling in scsi_debug drive
            utils.system("echo 1 > /sys/block/%s/queue/rotational"
                         % (host_file.split('/')[-1]))
            ret_file = host_file
            logging.debug("add_scsi_drive: add %s device", host_file)
        else:
            # Don't remove this device during cleanup
            # Reenable idling in scsi_debug drive (in case it's not)
            utils.system("echo 1 > /sys/block/%s/queue/rotational"
                         % (host_file.split('/')[-1]))
            ret_file = None
            logging.debug("add_scsi_drive: using %s device", host_file)

        out = vm.monitor.cmd("pci_add auto storage file=%s,if=%s,snapshot=off,"
                             "cache=off" % (host_file, driver))
        dev = re.search(r'OK domain (\d+), bus (\d+), slot (\d+), function \d+',
                        out)
        if not dev:
            raise error.TestFail("Can't add device(%s, %s, %s): %s" % (vm.name,
                                                        host_file, driver, out))
        device = "%02x:%02x" % (int(dev.group(2)), int(dev.group(3)))
        time.sleep(3)
        out = vm.monitor.info('qtree', debug=False)
        if out.count('addr %s.0' % device) != 1:
            raise error.TestFail("Can't add device(%s, %s, %s): device in qtree"
                            ":\n%s" % (vm.name, host_file.name, driver, out))
        return (ret_file, device)


    def rm_drive(vm, host_file, device):
        """
        Remove drive from vm and device on disk
        ! beware to remove scsi devices in reverse order !
        """
        err = False
        # TODO: Implement also via QMP
        vm.monitor.cmd("pci_del %s" % device)
        time.sleep(3)
        qtree = vm.monitor.info('qtree', debug=False)
        if qtree.count('addr %s.0' % device) != 0:
            err = True
            vm.destroy()

        if isinstance(host_file, str):    # scsi device
            utils.system("echo -1> /sys/bus/pseudo/drivers/scsi_debug/add_host")
        else:     # file
            host_file.close()

        if err:
            logging.error("Cant del device(%s, %s, %s):\n%s", vm.name,
                                                    host_file, device, qtree)


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
                for i in range(1, -1, -1):
                    rm_drive(vms[i], self.files[i], self.devices[i])
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
            if get_device_driver() != 'virtio':
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
            blkio.initialize(self.modules)
            for i in range(2):
                pwd.append(blkio.mk_cgroup())
                blkio.set_cgroup(self.vms[i].get_shell_pid(), pwd[i])
                # Move all existing threads into cgroup
                for tmp in utils.get_children_pids(self.vms[i].get_shell_pid()):
                    blkio.set_cgroup(int(tmp), pwd[i])
            self.blkio.set_property("blkio.weight", 100, pwd[0])
            self.blkio.set_property("blkio.weight", 1000, pwd[1])

            for i in range(2):
                (host_file, device) = add_file_drive(vms[i], "virtio")
                self.files.append(host_file)
                self.devices.append(device)

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
            if out1 == 0:
                raise error.TestFail("No data transfered: %d:%d (1:10)" %
                                      (out1, out2))
            if out1*3  > out2:
                raise error.TestFail("dd values: %d:%d (1:%.2f), limit 1:3"
                                     ", theoretical: 1:10"
                                     % (out1, out2, out2/out1))
            else:
                logging.info("dd values: %d:%d (1:%.2f)", out1, out2, out2/out1)
            return "dd values: %d:%d (1:%.2f)" % (out1, out2, out2/out1)



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
            self.dd_cmd = get_dd_cmd("read", bs="100K")


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
            self.dd_cmd = get_dd_cmd("write", bs="100K")


    class _TestBlkioThrottle:
        """
        BlkioThrottle dummy test
         * Use it as a base class to an actual test!
         * self.dd_cmd and throughputs have to be implemented
         * It prepares a vm and runs self.dd_cmd. Always after 1 minute switches
           the cgroup. At the end verifies, that the throughputs matches the
           theoretical values.
        """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            self.vm = vms[0]    # Virt machines
            self.modules = modules  # cgroup module handler
            self.cgroup = Cgroup('blkio', '')   # cgroup blkio handler
            self.cgroups = []   # List of cgroups directories
            self.files = None   # Temporary files (files of virt disks)
            self.devices = None # Temporary virt devices (PCI drive 1 per vm)
            self.dd_cmd = None  # DD command used to test the throughput
            self.speeds = None  # cgroup throughput
            if get_device_driver() == "virtio":
                self.dev = "vd?"
            else:
                self.dev = "[sh]d?"

        def cleanup(self):
            """
            Cleanup
            """
            err = ""
            try:
                rm_drive(self.vm, self.files, self.devices)
            except Exception, failure_detail:
                err += "\nCan't remove PCI drive: %s" % failure_detail
            try:
                del(self.cgroup)
            except Exception, failure_detail:
                err += "\nCan't remove Cgroup: %s" % failure_detail

            if err:
                logging.error("Some cleanup operations failed: %s", err)
                raise error.TestError("Some cleanup operations failed: %s"
                                      % err)

        def init(self):
            """
            Initialization
             * creates a new virtio device and adds it into vm
             * creates a cgroup for each throughput
            """
            if (self.dd_cmd is None) or (self.speeds) is None:
                raise error.TestError("Corrupt class, aren't you trying to run "
                                      "parent _TestBlkioThrottle() function?")

            if get_device_driver() == "ide":
                logging.warn("The main disk for this VM is ide wich doesn't "
                             "support hot-plug. Using virtio_blk instead")
                (self.files, self.devices) = add_scsi_drive(self.vm,
                                                            driver="virtio")
            else:
                (self.files, self.devices) = add_scsi_drive(self.vm)
            try:
                dev = utils.system_output("ls -l %s" % self.files).split()[4:6]
                dev[0] = dev[0][:-1]    # Remove tailing ','
            except:
                time.sleep(5)
                raise error.TestFail("Couldn't get %s maj and min numbers"
                                     % self.files)

            cgroup = self.cgroup
            cgroup.initialize(self.modules)
            for i in range(len(self.speeds)):
                speed = self.speeds[i]
                self.cgroups.append(cgroup.mk_cgroup())
                if speed == 0:  # Disable limit (removes the limit)
                    cgroup.set_property("blkio.throttle.write_bps_device",
                                        "%s:%s %s" % (dev[0], dev[1], speed),
                                        check="")
                    cgroup.set_property("blkio.throttle.read_bps_device",
                                        "%s:%s %s" % (dev[0], dev[1], speed),
                                        check="")
                else:       # Enable limit (input separator ' ', output '\t')
                    cgroup.set_property("blkio.throttle.write_bps_device",
                                        "%s:%s %s" % (dev[0], dev[1], speed),
                                        self.cgroups[i], check="%s:%s\t%s"
                                                    % (dev[0], dev[1], speed))
                    cgroup.set_property("blkio.throttle.read_bps_device",
                                        "%s:%s %s" % (dev[0], dev[1], speed),
                                        self.cgroups[i], check="%s:%s\t%s"
                                                    % (dev[0], dev[1], speed))

        def run(self):
            """
            Actual test:
             * executes self.dd_cmd in vm while limiting it's throughput using
               different cgroups (or in a special case only one). At the end
               it verifies the throughputs.
            """
            out = []
            sessions = []
            sessions.append(self.vm.wait_for_login(timeout=30))
            sessions.append(self.vm.wait_for_login(timeout=30))
            sessions[0].sendline(self.dd_cmd)
            for i in range(len(self.cgroups)):
                logging.info("Limiting speed to: %s", (self.speeds[i]))
                # Assign all threads of vm
                self.cgroup.set_cgroup(self.vm.get_shell_pid(), self.cgroups[i])
                for pid in utils.get_children_pids(self.vm.get_shell_pid()):
                    self.cgroup.set_cgroup(int(pid), self.cgroups[i])

                # Standard test-time is 60s. If the slice time is less than 30s,
                # test-time is prolonged to 30s per slice.
                time.sleep(max(60/len(self.speeds), 30))
                sessions[1].sendline("rm -f /tmp/cgroup_lock; killall -9 dd")
                out.append(sessions[0].read_up_to_prompt())
                sessions[0].sendline(self.dd_cmd)
                time.sleep(random()*0.05)

            sessions[1].sendline("rm -f /tmp/cgroup_lock; killall -9 dd")
            # Verification
            re_dd = (r'(\d+) bytes \(\d+\.*\d* \w*\) copied, (\d+\.*\d*) s, '
                      '\d+\.*\d* \w./s')
            err = []
            for i in range(len(out)):
                out[i] = [int(int(_[0])/float(_[1]))
                              for _ in re.findall(re_dd, out[i])]
                if not out[i]:
                    raise error.TestFail("Not enough samples; please increase"
                                         "throughput speed or testing time;"
                                         "\nsamples: %s" % (out[i]))
                # First samples might be corrupted, use only last sample when
                # not enough data. (which are already an avg of 3xBS)
                warn = False
                if len(out[i]) < 3:
                    warn = True
                    out[i] = [out[i][-1]]
                count = len(out[i])
                out[i].sort()
                # out = [min, med, max, number_of_samples]
                out[i] = [out[i][0], out[i][count/2], out[i][-1], count]
                if warn:
                    logging.warn("Not enough samples, using the last one (%s)",
                                 out[i])
                if ((self.speeds[i] != 0) and
                        (distance(out[i][1], self.speeds[i]) > 0.1)):
                    logging.error("The throughput didn't match the requirements"
                                  "(%s !~ %s)", out[i], self.speeds[i])
                    err.append(i)

            if self.speeds.count(0) > 1:
                unlimited = []
                for i in range(len(self.speeds)):
                    if self.speeds[i] == 0:
                        unlimited.append(out[i][1])
                        self.speeds[i] = "(inf)"

                avg = sum(unlimited) / len(unlimited)
                if avg == 0:
                    logging.warn("Average unlimited speed is 0 (%s)", out)
                else:
                    for speed in unlimited:
                        if distance(speed, avg) > 0.1:
                            logging.warning("Unlimited speeds variates during "
                                            "the test: %s", unlimited)
                            break


            out_speeds = ["%s ~ %s" % (out[i][1], self.speeds[i])
                                        for i in range(len(self.speeds))]
            if err:
                if len(out) == 1:
                    raise error.TestFail("Actual throughput: %s, theoretical: "
                                         "%s" % (out[0][1], self.speeds[0]))
                elif len(err) == len(out):
                    raise error.TestFail("All throughput limits were broken "
                                         "(%s)" % (out_speeds))
                else:
                    raise error.TestFail("Limits (%s) were broken (%s)"
                                         % (err, out_speeds))

            return ("All throughputs matched their limits (%s)" % out_speeds)


    class TestBlkioThrottleRead(_TestBlkioThrottle):
        """ Tests the blkio.throttle.read_bps_device """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            _TestBlkioThrottle.__init__(self, vms, modules)
            self.dd_cmd = get_dd_cmd("read", dev=self.dev, count=1)
            self.speeds = [1024]


    class TestBlkioThrottleWrite(_TestBlkioThrottle):
        """ Tests the blkio.throttle.write_bps_device """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            _TestBlkioThrottle.__init__(self, vms, modules)
            self.dd_cmd = get_dd_cmd("write", dev=self.dev, count=1)
            self.speeds = [1024]


    class TestBlkioThrottleMultipleRead(_TestBlkioThrottle):
        """
        Tests the blkio.throttle.read_bps_device while switching multiple
        cgroups with different speeds.
        """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            _TestBlkioThrottle.__init__(self, vms, modules)
            self.dd_cmd = get_dd_cmd("read", dev=self.dev, count=1)
            self.speeds = [0, 1024, 0, 2048, 0, 4096]


    class TestBlkioThrottleMultipleWrite(_TestBlkioThrottle):
        """
        Tests the blkio.throttle.write_bps_device while switching multiple
        cgroups with different speeds.
        """
        def __init__(self, vms, modules):
            """
            Initialization
            @param vms: list of vms
            @param modules: initialized cgroup module class
            """
            _TestBlkioThrottle.__init__(self, vms, modules)
            self.dd_cmd = get_dd_cmd("write", dev=self.dev, count=1)
            self.speeds = [0, 1024, 0, 2048, 0, 4096]


    # Setup
    # TODO: Add all new tests here
    tests = {"blkio_bandwidth_weigth_read"  : TestBlkioBandwidthWeigthRead,
             "blkio_bandwidth_weigth_write" : TestBlkioBandwidthWeigthWrite,
             "blkio_throttle_read"          : TestBlkioThrottleRead,
             "blkio_throttle_write"         : TestBlkioThrottleWrite,
             "blkio_throttle_multiple_read" : TestBlkioThrottleMultipleRead,
             "blkio_throttle_multiple_write" : TestBlkioThrottleMultipleWrite,
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
                err = ""
                try:
                    tst = tests[cg_test](vms, modules)
                    tst.init()
                    out = tst.run()
                except error.TestFail, failure_detail:
                    logging.error("%s: Leaving, test FAILED (TestFail): %s",
                                  cg_test, failure_detail)
                    err += "test, "
                    out = failure_detail
                except error.TestError, failure_detail:
                    tb = utils.etraceback(cg_test, sys.exc_info())
                    logging.error("%s: Leaving, test FAILED (TestError): %s",
                                  cg_test, tb)
                    err += "testErr, "
                    out = failure_detail
                except Exception, failure_detail:
                    tb = utils.etraceback(cg_test, sys.exc_info())
                    logging.error("%s: Leaving, test FAILED (Exception): %s",
                                  cg_test, tb)
                    err += "testUnknownErr, "
                    out = failure_detail

                try:
                    tst.cleanup()
                except Exception, failure_detail:
                    logging.warn("%s: cleanup failed: %s\n", failure_detail)
                    err += "cleanup, "

                try:
                    _check_vms(vms)
                except Exception, failure_detail:
                    logging.warn("%s: _check_vms failed: %s\n", failure_detail)
                    err += "VM check, "

                if err.startswith("test"):
                    results += ("\n [F] %s: {%s} FAILED: %s" %
                                 (cg_test, err[:-2], out))
                elif err:
                    results += ("\n [E] %s: Test passed but {%s} FAILED: %s" %
                                 (cg_test, err[:-2], out))
                else:
                    results += ("\n [P] %s: PASSED: %s" % (cg_test, out))

    out = ("SUM: All tests finished (%d PASS / %d FAIL = %d TOTAL)%s" %
           (results.count("PASSED"), results.count("FAILED"),
            (results.count("PASSED")+results.count("FAILED")), results))
    logging.info(out)
    if results.count("FAILED"):
        raise error.TestFail("Some subtests failed\n%s" % out)
