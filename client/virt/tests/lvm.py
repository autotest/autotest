import logging, os
from autotest_lib.client.common_lib import error


@error.context_aware
def mount_lv(lv_path, session):
    error.context("mounting ext3 filesystem made on logical volume %s" %
                  os.path.basename(lv_path))
    session.cmd("mkdir -p /mnt/kvm_test_lvm")
    session.cmd("mount %s /mnt/kvm_test_lvm" % lv_path)


@error.context_aware
def umount_lv(lv_path, session):
    error.context("umounting ext3 filesystem made on logical volume %s" %
                  os.path.basename(lv_path))
    session.cmd("umount %s" % lv_path)
    session.cmd("rm -rf /mnt/kvm_test_lvm")


@error.context_aware
def run_lvm(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Create a volume group and add both disks as pv to the Group
    3) Create a logical volume on the VG
    5) `fsck' to check the partition that LV locates

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    vg_name = "vg_kvm_test"
    lv_name = "lv_kvm_test"
    lv_path = "/dev/%s/%s" % (vg_name, lv_name)
    disks = params.get("disks", "/dev/hdb /dev/hdc")
    clean = params.get("clean", "yes")
    timeout = params.get("lvm_timeout", "600")

    try:
        error.context("adding physical volumes %s" % disks)
        session.cmd("pvcreate %s" % disks)

        error.context("creating a volume group out of %s" % disks)
        session.cmd("vgcreate %s %s" % (vg_name, disks))

        error.context("activating volume group %s" % vg_name)
        session.cmd("vgchange -ay %s" % vg_name)

        error.context("creating logical volume on volume group %s" % vg_name)
        session.cmd("lvcreate -L2000 -n %s %s" % (lv_name, vg_name))

        error.context("creating ext3 filesystem on logical volume %s" % lv_name)
        session.cmd("yes | mkfs.ext3 %s" % lv_path, timeout=int(timeout))

        mount_lv(lv_path, session)

        umount_lv(lv_path, session)

        error.context("checking ext3 filesystem made on logical volume %s" %
                      lv_name)
        session.cmd("fsck %s" % lv_path, timeout=int(timeout))

        if clean == "no":
            mount_lv(lv_path, session)

    finally:
        if clean == "yes":
            umount_lv(lv_path, session)

            error.context("removing logical volume %s" % lv_name)
            session.cmd("lvremove %s" % lv_name)

            error.context("disabling volume group %s" % vg_name)
            session.cmd("vgchange -a n %s" % vg_name)

            error.context("removing volume group %s" % vg_name)
            session.cmd("vgremove -f %s" % vg_name)
