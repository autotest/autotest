"""
Test that automatically takes shapshots from existing logical volumes
or creates them.
"""

import logging
import re, os, shutil, time

from autotest.client import utils, test
from autotest.client.shared import error

# size in MB
RAMDISK_VG_SIZE = "40000"
RAMDISK_BASEDIR = "/tmp"
RAMDISK_SPARSE_FILENAME = "virtual_hdd"


class lvsetup(test.test):
    """
    Test class inheriting from test with main method run_once().

    If this test turns into a library the constants at its beginning should
    be converted to class attributes and initiated in a constructor.
    """
    version = 1

    @error.context_aware
    def _vg_ramdisk(self, vg_name):
        """
        Create vg on top of ram memory to speed up lv performance.
        """
        error.context("Creating virtual group on top of ram memory",
                      logging.info)
        vg_size = RAMDISK_VG_SIZE
        vg_ramdisk_dir = os.path.join(RAMDISK_BASEDIR, vg_name)
        ramdisk_filename = os.path.join(vg_ramdisk_dir,
                                        RAMDISK_SPARSE_FILENAME)

        self._vg_ramdisk_cleanup(ramdisk_filename,
                                 vg_ramdisk_dir, vg_name, "")
        result = ""
        if not os.path.exists(vg_ramdisk_dir):
            os.mkdir(vg_ramdisk_dir)
        try:
            logging.info("Mounting tmpfs")
            result = utils.run("mount -t tmpfs tmpfs " + vg_ramdisk_dir)

            logging.info("Converting and copying /dev/zero")
            cmd = ("dd if=/dev/zero of=" + ramdisk_filename +
                   " bs=1M count=1 seek=" + vg_size)
            result = utils.run(cmd, verbose=True)

            logging.info("Finding free loop device")
            result = utils.run("losetup --find", verbose=True)
        except error.CmdError, ex:
            logging.error(ex)
            self._vg_ramdisk_cleanup(ramdisk_filename,
                                     vg_ramdisk_dir, vg_name, "")
            raise ex

        loop_device = result.stdout.rstrip()

        try:
            logging.info("Creating loop device")
            result = utils.run("losetup " + loop_device
                               + " " + ramdisk_filename)
            logging.info("Creating physical volume %s", loop_device)
            result = utils.run("pvcreate " + loop_device)
            logging.info("Creating volume group %s", vg_name)
            result = utils.run("vgcreate " + vg_name
                               + " " + loop_device)
        except error.CmdError, ex:
            logging.error(ex)
            self._vg_ramdisk_cleanup(ramdisk_filename, vg_ramdisk_dir,
                                     vg_name, loop_device)
            raise ex

        logging.info(result.stdout.rstrip())


    def _vg_ramdisk_cleanup(self, ramdisk_filename, vg_ramdisk_dir,
                            vg_name, loop_device):
        """
        Inline cleanup function in case of test error.
        """
        result = utils.run("vgremove " + vg_name, ignore_status=True)
        if result.exit_status == 0:
            logging.info(result.stdout.rstrip())
        else:
            logging.debug("%s -> %s", result.command, result.stderr)

        result = utils.run("pvremove " + loop_device, ignore_status=True)
        if result.exit_status == 0:
            logging.info(result.stdout.rstrip())
        else:
            logging.debug("%s -> %s", result.command, result.stderr)

        for _ in range(10):
            time.sleep(0.1)
            result = utils.run("losetup -d " + loop_device, ignore_status=True)
            if "resource busy" not in result.stderr:
                if result.exit_status != 0:
                    logging.debug("%s -> %s", result.command, result.stderr)
                else:
                    logging.info("Loop device %s deleted", loop_device)
                break

        if os.path.exists(ramdisk_filename):
            os.unlink(ramdisk_filename)
            logging.info("Ramdisk filename %s deleted", ramdisk_filename)

        utils.run("umount " + vg_ramdisk_dir, ignore_status=True)
        if result.exit_status == 0:
            if loop_device != "":
                logging.info("Loop device %s unmounted", loop_device)
        else:
            logging.debug("%s -> %s", result.command, result.stderr)

        if os.path.exists(vg_ramdisk_dir):
            try:
                shutil.rmtree(vg_ramdisk_dir)
                logging.info("Ramdisk directory %s deleted", vg_ramdisk_dir)
            except OSError:
                pass


    def _vg_check(self, vg_name):
        """
        Check whether provided volume group exists.
        """
        cmd = "vgdisplay " + vg_name
        try:
            utils.run(cmd)
            logging.info("Provided volume group exists: " + vg_name)
            return True
        except error.CmdError:
            return False


    def _vg_create(self, vg_name):
        """
        Create volume group.
        """
        cmd = "vgdisplay " + vg_name
        try:
            utils.run(cmd)
            logging.info("Provided volume group exists: " + vg_name)
            return True
        except error.CmdError:
            return False


    def _lv_check(self, vg_name, lv_name):
        """
        Check whether provided logical volume exists.
        """
        cmd = "lvdisplay"
        result = utils.run(cmd, ignore_status=True)

        # unstable approach but currently works
        lvpattern = r"LV Path\s+/dev/" + vg_name + r"/" + lv_name + "\s+"
        match = re.search(lvpattern, result.stdout.rstrip())
        if match:
            logging.info("Provided logical volume exists: /dev/" +
                        vg_name + "/" + lv_name)
            return True
        else:
            return False


    @error.context_aware
    def _lv_remove(self, vg_name, lv_name):
        """
        Remove a logical volume.
        """
        error.context("Removing volume /dev/%s/%s" %
                      (vg_name, lv_name), logging.info)
        cmd = "lvremove -f " + vg_name + "/" + lv_name
        result = utils.run(cmd)
        logging.info(result.stdout.rstrip())


    @error.context_aware
    def _lv_create(self, vg_name, lv_name, lv_size):
        """
        Create a logical volume.
        """
        error.context("Creating origin lv to take a snapshot from",
                      logging.info)
        cmd = ("lvcreate --size " + lv_size +
                " --name " + lv_name + " " +
                vg_name)
        result = utils.run(cmd)
        logging.info(result.stdout.rstrip())


    @error.context_aware
    def _lv_revert(self, vg_name, lv_snapshot_name):
        """
        Revert the origin to a snapshot.
        """
        error.context("Reverting origin to snapshot", logging.info)
        cmd = ("lvconvert --merge /dev/%s/%s"
              % (vg_name, lv_snapshot_name))
        result = utils.run(cmd)
        logging.info(result.stdout.rstrip())


    @error.context_aware
    def _lv_take_snapshot(self, vg_name, lv_name,
                          lv_snapshot_name, lv_snapshot_size):
        """
        Take a snapshot of the original logical volume.
        """
        error.context("Taking snapshot from origin", logging.info)
        cmd = ("lvcreate --size " + lv_snapshot_size + " --snapshot " +
                " --name " + lv_snapshot_name +
                " /dev/" + vg_name + "/" + lv_name)
        result = utils.run(cmd)
        logging.info(result.stdout.rstrip())


    def run_once(self, vg_name='autotest_vg', lv_name='autotest_lv',
                 lv_size='1G', lv_snapshot_name='autotest_sn',
                 lv_snapshot_size='1G', override_flag=0):
        """
        General logical volume setup.

        The main part of the lvm setup checks whether the provided volume group
        exists and if not, creates one from the ramdisk. It then creates a logical
        volume if there is no logical volume, takes a snapshot from the logical
        if there is logical volume but no snapshot, and merges with the snapshot
        if both the snapshot and the logical volume are present.

        @param vg_name: Name of the volume group.
        @param lv_name: Name of the logical volume.
        @param lv_size: Size of the logical volume as string in the form "#G"
                (for example 30G).
        @param lv_snapshot_name: Name of the snapshot with origin the logical
                volume.
        @param lv_snapshot_size: Size of the snapshot with origin the logical
                volume also as "#G".
        @param override_flag: Flag to override default policy. Override flag
                can be set to -1 to force remove, 1 to force create, and 0
                for default policy.
        """
        # if no virtual group is defined create one based on ramdisk
        if not self._vg_check(vg_name):
            self._vg_ramdisk(vg_name)

        # if no snapshot is defined start fresh logical volume
        if override_flag == 1 and self._lv_check(vg_name, lv_name):
            self._lv_remove(vg_name, lv_name)
            self._lv_create(vg_name, lv_name, lv_size)
        elif override_flag == -1 and self._lv_check(vg_name, lv_name):
            self._lv_remove(vg_name, lv_name)
        else:

            # perform normal check policy
            if (self._lv_check(vg_name, lv_snapshot_name)
                and self._lv_check(vg_name, lv_name)):
                self._lv_revert(vg_name, lv_snapshot_name)
                self._lv_take_snapshot(vg_name, lv_name,
                                       lv_snapshot_name,
                                       lv_snapshot_size)

            elif (self._lv_check(vg_name, lv_snapshot_name)
                and not self._lv_check(vg_name, lv_name)):
                raise error.TestError("Snapshot origin not found")

            elif (not self._lv_check(vg_name, lv_snapshot_name)
                and self._lv_check(vg_name, lv_name)):
                self._lv_take_snapshot(vg_name, lv_name,
                                       lv_snapshot_name,
                                       lv_snapshot_size)

            else:
                self._lv_create(vg_name, lv_name, lv_size)
