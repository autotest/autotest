"""
KVM cdrom test
@author: Amos Kong <akong@redhat.com>
@author: Lucas Meneghel Rodrigues <lmr@redhat.com>
@author: Lukas Doktor <ldoktor@redhat.com>
@copyright: 2011 Red Hat, Inc.
"""
import logging, re, time, os
from autotest.client.shared import error
from autotest.client import utils
from autotest.client.virt import virt_utils, aexpect, kvm_monitor


@error.context_aware
def run_cdrom(test, params, env):
    """
    KVM cdrom test:

    1) Boot up a VM with one iso.
    2) Check if VM identifies correctly the iso file.
    3) * If cdrom_test_autounlock is set, verifies that device is unlocked
       <300s after boot
    4) Eject cdrom using monitor and change with another iso several times.
    5) * If cdrom_test_tray_status = yes, tests tray reporting.
    6) Try to format cdrom and check the return string.
    7) Mount cdrom device.
    8) Copy file from cdrom and compare files using diff.
    9) Umount and mount several times.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.

    @param cfg: workaround_eject_time - Some versions of qemu are unable to
                                        eject CDROM directly after insert
    @param cfg: cdrom_test_autounlock - Test whether guest OS unlocks cdrom
                                        after boot (<300s after VM is booted)
    @param cfg: cdrom_test_tray_status - Test tray reporting (eject and insert
                                         CD couple of times in guest).

    @warning: Check dmesg for block device failures
    """
    def master_cdroms(params):
        """ Creates 'new' cdrom with one file on it """
        error.context("creating test cdrom")
        os.chdir(test.tmpdir)
        cdrom_cd1 = params.get("cdrom_cd1")
        if not os.path.isabs(cdrom_cd1):
            cdrom_cd1 = os.path.join(test.bindir, cdrom_cd1)
        cdrom_dir = os.path.dirname(cdrom_cd1)
        utils.run("dd if=/dev/urandom of=orig bs=10M count=1")
        utils.run("dd if=/dev/urandom of=new bs=10M count=1")
        utils.run("mkisofs -o %s/orig.iso orig" % cdrom_dir)
        utils.run("mkisofs -o %s/new.iso new" % cdrom_dir)
        return "%s/new.iso" % cdrom_dir

    def cleanup_cdroms(cdrom_dir):
        """ Removes created cdrom """
        error.context("cleaning up temp cdrom images")
        os.remove("%s/new.iso" % cdrom_dir)

    def get_cdrom_file(device):
        """
        @param device: qemu monitor device
        @return: file associated with $device device
        """
        blocks = vm.monitor.info("block")
        cdfile = None
        if isinstance(blocks, str):
            cdfile = re.findall('%s: .*file=(\S*) ' % device, blocks)
            if not cdfile:
                return None
            else:
                cdfile = cdfile[0]
        else:
            for block in blocks:
                if block['device'] == device:
                    try:
                        cdfile = block['inserted']['file']
                    except KeyError:
                        continue
        return cdfile

    def check_cdrom_tray(cdrom):
        """ Checks whether the tray is opend """
        blocks = vm.monitor.info("block")
        if isinstance(blocks, str):
            for block in blocks.splitlines():
                if cdrom in block:
                    if "tray-open=1" in block:
                        return True
                    elif "tray-open=0" in block:
                        return False
        else:
            for block in blocks:
                if block['device'] == cdrom and 'tray_open' in block.keys():
                    return block['tray_open']
        return None

    def eject_cdrom(device, monitor):
        """ Ejects the cdrom using kvm-monitor """
        if isinstance(monitor, kvm_monitor.HumanMonitor):
            monitor.cmd("eject %s" % device)
        elif isinstance(monitor, kvm_monitor.QMPMonitor):
            monitor.cmd("eject", args={'device': device})

    def change_cdrom(device, target, monitor):
        """ Changes the medium using kvm-monitor """
        if isinstance(monitor, kvm_monitor.HumanMonitor):
            monitor.cmd("change %s %s" % (device, target))
        elif isinstance(monitor, kvm_monitor.QMPMonitor):
            monitor.cmd("change", args={'device': device, 'target': target})

    cdrom_new = master_cdroms(params)
    cdrom_dir = os.path.dirname(cdrom_new)
    vm = env.get_vm(params["main_vm"])
    vm.create()

    # Some versions of qemu are unable to eject CDROM directly after insert
    workaround_eject_time = float(params.get('workaround_eject_time', 0))

    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))
    cdrom_orig = params.get("cdrom_cd1")
    if not os.path.isabs(cdrom_orig):
        cdrom_orig = os.path.join(test.bindir, cdrom_orig)
    cdrom = cdrom_orig
    output = session.get_command_output("ls /dev/cdrom*")
    cdrom_dev_list = re.findall("/dev/cdrom-\w+|/dev/cdrom\d*", output)
    logging.debug("cdrom_dev_list: %s", cdrom_dev_list)

    cdrom_dev = ""
    test_cmd = "dd if=%s of=/dev/null bs=1 count=1"
    for d in cdrom_dev_list:
        try:
            output = session.cmd(test_cmd % d)
            cdrom_dev = d
            break
        except aexpect.ShellError:
            logging.error(output)
    if not cdrom_dev:
        raise error.TestFail("Could not find a valid cdrom device")

    error.context("Detecting the existence of a cdrom")
    cdfile = cdrom
    device = vm.get_block({'file': cdfile})
    if not device:
        device = vm.get_block({'backing_file': cdfile})
        if not device:
            raise error.TestFail("Could not find a valid cdrom device")

    session.get_command_output("umount %s" % cdrom_dev)
    if params.get('cdrom_test_autounlock') == 'yes':
        error.context("Trying to unlock the cdrom")
        if not virt_utils.wait_for(lambda: not vm.check_block_locked(device),
                                   300):
            raise error.TestFail("Device %s could not be unlocked" % device)

    max_times = int(params.get("max_times", 100))
    error.context("Eject the cdrom in monitor %s times" % max_times)
    for i in range(1, max_times):
        session.cmd('eject %s' % cdrom_dev)
        eject_cdrom(device, vm.monitor)
        if get_cdrom_file(device) is not None:
            raise error.TestFail("Device %s was not ejected (%s)" % (cdrom, i))

        cdrom = cdrom_new
        # On even attempts, try to change the cdrom
        if i % 2 == 0:
            cdrom = cdrom_orig
        change_cdrom(device, cdrom, vm.monitor)
        if get_cdrom_file(device) != cdrom:
            raise error.TestFail("It wasn't possible to change cdrom %s (%s)"
                                  % (cdrom, i))
        time.sleep(workaround_eject_time)

    error.context('Eject the cdrom in guest %s times' % max_times)
    if params.get('cdrom_test_tray_status') != 'yes':
        pass
    elif check_cdrom_tray(device) is None:
        logging.error("Tray reporting not supported by qemu!")
        logging.error("cdrom_test_tray_status skipped...")
    else:
        for i in range(1, max_times):
            session.cmd('eject %s' % cdrom_dev)
            if not check_cdrom_tray(device):
                raise error.TestFail("Monitor reports closed tray (%s)" % i)
            session.cmd('dd if=%s of=/dev/null count=1' % cdrom_dev)
            if check_cdrom_tray(device):
                raise error.TestFail("Monitor reports opened tray (%s)" % i)
            time.sleep(workaround_eject_time)

    error.context("Check whether the cdrom is read-only")
    try:
        output = session.cmd("echo y | mkfs %s" % cdrom_dev)
        raise error.TestFail("Attempt to format cdrom %s succeeded" %
                                                                    cdrom_dev)
    except aexpect.ShellError:
        pass

    error.context("Mounting the cdrom under /mnt")
    session.cmd("mount %s %s" % (cdrom_dev, "/mnt"), timeout=30)

    filename = "new"

    error.context("File copying test")
    session.cmd("rm -f /tmp/%s" % filename)
    session.cmd("cp -f /mnt/%s /tmp/" % filename)

    error.context("Compare file on disk and on cdrom")
    f1_hash = session.cmd("md5sum /mnt/%s" % filename).split()[0].strip()
    f2_hash = session.cmd("md5sum /tmp/%s" % filename).split()[0].strip()
    if f1_hash != f2_hash:
        raise error.TestFail("On disk and on cdrom files are different, "
                             "md5 mismatch")

    error.context("Mount/Unmount cdrom for %s times" % max_times)
    for i in range(1, max_times):
        try:
            session.cmd("umount %s" % cdrom_dev)
            session.cmd("mount %s /mnt" % cdrom_dev)
        except aexpect.ShellError:
            logging.debug(session.cmd("cat /etc/mtab"))
            raise

    session.cmd("umount %s" % cdrom_dev)

    error.context("Cleanup")
    # Return the cdrom_orig
    cdfile = get_cdrom_file(device)
    if cdfile != cdrom_orig:
        time.sleep(workaround_eject_time)
        session.cmd('eject %s' % cdrom_dev)
        eject_cdrom(device, vm.monitor)
        if get_cdrom_file(device) is not None:
            raise error.TestFail("Device %s was not ejected (%s)" % (cdrom, i))

        change_cdrom(device, cdrom_orig, vm.monitor)
        if get_cdrom_file(device) != cdrom_orig:
            raise error.TestFail("It wasn't possible to change cdrom %s (%s)"
                                  % (cdrom, i))

    session.close()
    cleanup_cdroms(cdrom_dir)
