"""
Image operate class and functions

This exports:
  - two functions for get image/blkdebug filename
  - class for image operates and basic parameters
"""
from autotest.client.shared import error
from autotest.client import utils
import virt_utils
import virt_vm
import logging
import os
import shutil
import re

# Functions for handling virtual machine image files

def get_image_blkdebug_filename(params, root_dir):
    """
    Generate an blkdebug file path from params and root_dir.

    blkdebug files allow error injection in the block subsystem.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           blkdebug -- the name of the debug file.
    """
    blkdebug_name = params.get("drive_blkdebug", None)
    if blkdebug_name is not None:
        blkdebug_filename = virt_utils.get_path(root_dir, blkdebug_name)
    else:
        blkdebug_filename = None
    return blkdebug_filename


def get_image_filename(params, root_dir):
    """
    Generate an image path from params and root_dir.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    @raise VMDeviceError: When no matching disk found (in indirect method).
    """
    image_name = params.get("image_name", "image")
    indirect_image_select = params.get("indirect_image_select")
    if indirect_image_select:
        re_name = image_name
        indirect_image_select = int(indirect_image_select)
        matching_images = utils.system_output("ls -1d %s" % re_name)
        matching_images = sorted(matching_images.split('\n'))
        if matching_images[-1] == '':
            matching_images = matching_images[:-1]
        try:
            image_name = matching_images[indirect_image_select]
        except IndexError:
            raise virt_vm.VMDeviceError("No matching disk found for "
                                        "name = '%s', matching = '%s' and "
                                        "selector = '%s'" %
                                        (re_name, matching_images,
                                         indirect_image_select))
        for protected in params.get('indirect_image_blacklist', '').split(' '):
            if re.match(protected, image_name):
                raise virt_vm.VMDeviceError("Matching disk is in blacklist. "
                                            "name = '%s', matching = '%s' and "
                                            "selector = '%s'" %
                                            (re_name, matching_images,
                                             indirect_image_select))
    image_format = params.get("image_format", "qcow2")
    if params.get("image_raw_device") == "yes":
        return image_name
    if image_format:
        image_filename = "%s.%s" % (image_name, image_format)
    else:
        image_filename = image_name
    image_filename = virt_utils.get_path(root_dir, image_filename)
    return image_filename


class OptionMissing(Exception):
    """
    Option not find in the odbject
    """
    def __init__(self, option):
        self.option = option


    def __str__(self):
        return "%s is missing. Please check your parameters" % self.option


class QemuImg():
    """
    A class for do operation to images
    """
    def __init__(self, params, root_dir, tag):
        self.image_filename = get_image_filename(params, root_dir)
        self.image_format = params.get("image_format", "qcow2")
        self.size = params.get("image_size", "10G")
        self.check_output = params.get("check_output") == "yes"
        self.image_blkdebug_filename = get_image_blkdebug_filename(params,
                                                                   root_dir)
        self.image_cmd = virt_utils.get_path(root_dir,
                                 params.get("qemu_img_binary","qemu-img"))
        image_chain = params.get("image_chain")
        self.base_tag = None
        self.snapshot_tag = None
        if image_chain:
            image_chain = re.split("\s+", image_chain)
            if tag in image_chain:
                index = image_chain.index(tag)
                if index < len(image_chain):
                    self.snapshot_tag = image_chain[index + 1]
                if index > 0:
                    self.base_tag = image_chain[index - 1]
        if self.base_tag:
            base_params = params.object_params(self.base_tag)
            self.base_image_filename = virt_utils.get_path(base_params,
                                                           root_dir)
            self.base_format = base_params.get("image_format")
        if self.snapshot_tag:
            ss_params = params.object_params(self.snapshot_tag)
            self.snapshot_image_filename = virt_utils.get_path(ss_params,
                                                               root_dir)
            self.snapshot_format = ss_params.get("image_format")
                    

    def check_option(self, option):
        """
        Check if object has the option required.
        """
        if option not in self.__dict__:
            raise OptionMissing(option)

    def create(self, params):
        """
        Create an image using qemu_image.
 
        @param params: Dictionary containing the test parameters.
 
        @note: params should contain:
               image_name -- the name of the image file, without extension
               image_format -- the format of the image (qcow2, raw etc)
               image_cluster_size (optional) -- the cluster size for the image
               image_size -- the requested size of the image (a string
               qemu-img can understand, such as '10G')
               create_with_dd -- use dd to create the image (raw format only)
               base_image(optional) -- the base image name when create
               snapshot
               base_format(optional) -- the format of base image
               encrypted(optional) -- if the image is encrypted, allowed
               values: on and off. Default is "off"
               preallocated(optional) -- if preallocation when create image,
               allowed values: off, metadata. Default is "off"
        """
        if params.get("create_with_dd") == "yes" and self.image_format == "raw":
            # maps K,M,G,T => (count, bs)
            human = {'K': (1, 1),
                     'M': (1, 1024),
                     'G': (1024, 1024),
                     'T': (1024, 1048576),
                    }
            if human.has_key(self.size[-1]):
                block_size = human[self.size[-1]][1]
                size = int(self.size[:-1]) * human[self.size[-1]][0]
            qemu_img_cmd = ("dd if=/dev/zero of=%s count=%s bs=%sK"
                            % (self.image_filename, size, block_size))
        else:
            qemu_img_cmd = self.image_cmd
            qemu_img_cmd += " create"
 
            qemu_img_cmd += " -f %s" % self.image_format
 
            image_cluster_size = params.get("image_cluster_size", None)
            preallocated = params.get("preallocated", "off")
            encrypted = params.get("encrypted", "off")

            if preallocated != "off":
                qemu_img_cmd += "-o preallocation=%s" % preallocated

            if encrypted != "off":
                qemu_img_cmd += ",encrypted=%s" % encrypted

            if image_cluster_size is not None:
                qemu_img_cmd += ",cluster_size=%s" % image_cluster_size

            if self.base_tag:
                qemu_img_cmd += " -b %s" % self.base_image_filename
                if self.base_format:
                    qemu_img_cmd += " -F %s" % self.base_format
 
            qemu_img_cmd += " %s" % self.image_filename
 
            qemu_img_cmd += " %s" % self.size

        check_output = params.get("check_output") == "yes"
        try:
            result = utils.system(qemu_img_cmd)
        except error.CmdError, e:
            logging.error("Could not create image, failed with error message:"
                            "%s", str(e))
            if not check_output:
                result = None
            else:
                result = str(e)
        if not check_output:
            result = self.image_filename

        return result



    def convert(self, params, root_dir):
        """
        Convert image

        @param params: A dict
        @param root_dir: dir for save the convert image

        @note: params should contain:
            convert_image_tag -- the image name of the convert image
            convert_filename -- the name of the image after convert
            convert_fmt -- the format after convert
            compressed -- indicates that target image must be compressed
            encrypted -- there are two value "off" and "on", 
            default value is "off"
        """
        convert_image_tag = params.get("image_convert")
        convert_image = params.get("image_name_%s" % convert_image_tag)
        convert_compressed = params.get("convert_compressed")
        convert_encrypted = params.get("convert_encrypted", "off")
        convert_format = params.get("image_format_%s" % convert_image_tag)
        params_convert = {"image_name": convert_image,
                          "image_format": convert_format}

        convert_image_filename = get_image_filename(params_convert, root_dir)

        cmd = self.image_cmd
        cmd += " convert"
        if convert_compressed == "yes":
            cmd += " -c"
        if convert_encrypted != "off":
            cmd += " -o encryption=%s" % convert_encrypted
        if self.image_format:
            cmd += " -f %s" % self.image_format
        cmd += " -O %s" % convert_format
        cmd += " %s %s" % (self.image_filename, convert_image_filename)

        logging.info("Convert image %s from %s to %s", self.image_filename,
                      self.image_format,convert_format)

        utils.system(cmd)

        return convert_image_tag



    def rebase(self, params):
        """
        Rebase image

        @param params: A dict

        @note: params should contain:
            cmd -- qemu-img cmd
            snapshot_img -- the snapshot name
            base_img -- base image name
            base_fmt -- base image format
            snapshot_fmt -- the snapshot format
            mode -- there are two value, "safe" and "unsafe",
            devault is "safe"
        """
        self.check_option("base_image_filename")
        self.check_option("base_format")

        rebase_mode = params.get("rebase_mode")
        cmd = self.image_cmd
        cmd += " rebase"
        if self.image_format:
            cmd += " -f %s" % self.image_format
        if rebase_mode == "unsafe":
            cmd += " -u"
        if self.base_tag:
            cmd += " -b %s -F %s %s" % (self.base_image_filename,
                                        self.base_format, self.image_filename)
        else:
            raise error.TestError("Can not find the image parameters need"
                                  " for rebase.")

        logging.info("Rebase snapshot %s to %s..." % (self.image_filename,
                                                    self.base_image_filename))
        utils.system(cmd)

        return self.base_tag



    def commit(self):
        """
        Commit image to it's base file
        """
        cmd = self.image_cmd
        cmd += " commit"
        cmd += " -f %s %s" % (self.image_format, self.image_filename)
        logging.info("Commit snapshot %s" % self.image_filename)
        utils.system(cmd)

        return self.image_filename


    def snapshot_create(self):
        """
        Create a snapshot image.

        @note: params should contain:
               snapshot_image_name -- the name of snapshot image file
        """

        cmd = self.image_cmd
        if self.snapshot_tag:
            cmd += " snapshot -c %s" % self.snapshot_image_filename
        else:
            raise error.TestError("Can not find the snapshot image"
                                  " parameters")
        cmd += " %s" % self.image_filename

        utils.system_output(cmd)

        return self.snapshot_tag


    def remove(self):
        """
        Remove an image file.
 
        @param params: A dict
 
        @note: params should contain:
               image_name -- the name of the image file, without extension
               image_format -- the format of the image (qcow2, raw etc)
        """
        logging.debug("Removing image file %s", self.image_filename)
        if os.path.exists(self.image_filename):
            os.unlink(self.image_filename)
        else:
            logging.debug("Image file %s not found", self.image_filename)



    def backup_image(self, params, root_dir, action, good=True):
        """
        Backup or restore a disk image, depending on the action chosen.
 
        @param params: Dictionary containing the test parameters.
        @param root_dir: Base directory for relative filenames.
        @param action: Whether we want to backup or restore the image.
        @param good: If we are backing up a good image(we want to restore it)
            or a bad image (we are saving a bad image for posterior analysis).

        @note: params should contain:
               image_name -- the name of the image file, without extension
               image_format -- the format of the image (qcow2, raw etc)
        """
        def backup_raw_device(src, dst):
            utils.system("dd if=%s of=%s bs=4k conv=sync" % (src, dst))
 
        def backup_image_file(src, dst):
            logging.debug("Copying %s -> %s", src, dst)
            shutil.copy(src, dst)
 
        def get_backup_name(filename, backup_dir, good):
            if not os.path.isdir(backup_dir):
                os.makedirs(backup_dir)
            basename = os.path.basename(filename)
            if good:
                backup_filename = "%s.backup" % basename
            else:
                backup_filename = ("%s.bad.%s" %
                                   (basename,
                                    virt_utils.generate_random_string(4)))
            return os.path.join(backup_dir, backup_filename)
 
 
        image_filename = self.image_filename
        backup_dir = params.get("backup_dir")
        if params.get('image_raw_device') == 'yes':
            iname = "raw_device"
            iformat = params.get("image_format", "qcow2")
            ifilename = "%s.%s" % (iname, iformat)
            ifilename = virt_utils.get_path(root_dir, ifilename)
            image_filename_backup = get_backup_name(ifilename, backup_dir, good)
            backup_func = backup_raw_device
        else:
            image_filename_backup = get_backup_name(image_filename, backup_dir,
                                                    good)
            backup_func = backup_image_file
 
        if action == 'backup':
            image_dir = os.path.dirname(image_filename)
            image_dir_disk_free = utils.freespace(image_dir)
            image_filename_size = os.path.getsize(image_filename)
            image_filename_backup_size = 0
            if os.path.isfile(image_filename_backup):
                image_filename_backup_size = os.path.getsize(
                                                        image_filename_backup)
            disk_free = image_dir_disk_free + image_filename_backup_size
            minimum_disk_free = 1.2 * image_filename_size
            if disk_free < minimum_disk_free:
                image_dir_disk_free_gb = float(image_dir_disk_free) / 10**9
                minimum_disk_free_gb = float(minimum_disk_free) / 10**9
                logging.error("Dir %s has %.1f GB free, less than the minimum "
                              "required to store a backup, defined to be 120%% "
                              "of the backup size, %.1f GB. Skipping backup...",
                              image_dir, image_dir_disk_free_gb,
                              minimum_disk_free_gb)
                return
            if good:
                # In case of qemu-img check return 1, we will make 2 backups,
                # one for investigation and other, to use as a 'pristine'
                # image for further tests
                state = 'good'
            else:
                state = 'bad'
            logging.info("Backing up %s image file %s", state, image_filename)
            src, dst = image_filename, image_filename_backup
        elif action == 'restore':
            if not os.path.isfile(image_filename_backup):
                logging.error('Image backup %s not found, skipping restore...',
                              image_filename_backup)
                return
            logging.info("Restoring image file %s from backup",
                         image_filename)
            src, dst = image_filename_backup, image_filename
 
        backup_func(src, dst)


    def clone_image(self, params, vm_name, image_name, root_dir):
        """
        Clone master image to vm specific file.
 
        @param params: Dictionary containing the test parameters.
        @param vm_name: Vm name.
        @param image_name: Master image name.
        @param root_dir: Base directory for relative filenames.
        """
        if not params.get("image_name_%s_%s" % (image_name, vm_name)):
            m_image_name = params.get("image_name", "image")
            vm_image_name = "%s_%s" % (m_image_name, vm_name)
            if params.get("clone_master", "yes") == "yes":
                image_params = params.object_params(image_name)
                image_params["image_name"] = vm_image_name
 
                m_image_fn = get_image_filename(params, root_dir)
                image_fn = get_image_filename(image_params, root_dir)
 
                logging.info("Clone master image for vms.")
                utils.run(params.get("image_clone_commnad") % (m_image_fn,
                                                               image_fn))
 
            params["image_name_%s_%s" % (image_name, vm_name)] = vm_image_name


    def rm_cloned_image(self, params, vm_name, image_name, root_dir):
        """
        Remove vm specific file.
 
        @param params: Dictionary containing the test parameters.
        @param vm_name: Vm name.
        @param image_name: Master image name.
        @param root_dir: Base directory for relative filenames.
        """
        if params.get("image_name_%s_%s" % (image_name, vm_name)):
            m_image_name = params.get("image_name", "image")
            vm_image_name = "%s_%s" % (m_image_name, vm_name)
            if params.get("clone_master", "yes") == "yes":
                image_params = params.object_params(image_name)
                image_params["image_name"] = vm_image_name
 
                image_fn = get_image_filename(image_params, root_dir)
 
                logging.debug("Removing vm specific image file %s", image_fn)
                if os.path.exists(image_fn):
                    utils.run(params.get("image_remove_commnad") % (image_fn))
                else:
                    logging.debug("Image file %s not found", image_fn)

    def check_image(self, params, root_dir):
        """
        Check an image using the appropriate tools for each virt backend.
 
        @param params: Dictionary containing the test parameters.
        @param root_dir: Base directory for relative filenames.
 
        @note: params should contain:
               image_name -- the name of the image file, without extension
               image_format -- the format of the image (qcow2, raw etc)
 
        @raise VMImageCheckError: In case qemu-img check fails on the image.
        """
        vm_type = params.get("vm_type")
        if vm_type == 'kvm':
            image_filename = self.image_filename
            logging.debug("Checking image file %s", image_filename)
            qemu_img_cmd = self.image_cmd 
            image_is_qcow2 = params.get("image_format") == 'qcow2'
            if os.path.exists(image_filename) and image_is_qcow2:
                # Verifying if qemu-img supports 'check'
                q_result = utils.run(qemu_img_cmd, ignore_status=True)
                q_output = q_result.stdout
                check_img = True
                if not "check" in q_output:
                    logging.error("qemu-img does not support 'check', "
                                  "skipping check")
                    check_img = False
                if not "info" in q_output:
                    logging.error("qemu-img does not support 'info', "
                                  "skipping check")
                    check_img = False
                if check_img:
                    try:
                        utils.system("%s info %s" % (qemu_img_cmd,
                                                     image_filename))
                    except error.CmdError:
                        logging.error("Error getting info from image %s",
                                      image_filename)
 
                    cmd_result = utils.run("%s check %s" %
                                           (qemu_img_cmd, image_filename),
                                           ignore_status=True)
                    # Error check, large chances of a non-fatal problem.
                    # There are chances that bad data was skipped though
                    if cmd_result.exit_status == 1:
                        for e_line in cmd_result.stdout.splitlines():
                            logging.error("[stdout] %s", e_line)
                        for e_line in cmd_result.stderr.splitlines():
                            logging.error("[stderr] %s", e_line)
                        chk = params.get("backup_image_on_check_error", "no")
                        if chk == "yes":
                            self.backup_image(params, root_dir, "backup", False)
                        raise error.TestWarn("qemu-img check error. Some bad "
                                             "data in the image may have gone"
                                             " unnoticed")
                    # Exit status 2 is data corruption for sure,
                    # so fail the test
                    elif cmd_result.exit_status == 2:
                        for e_line in cmd_result.stdout.splitlines():
                            logging.error("[stdout] %s", e_line)
                        for e_line in cmd_result.stderr.splitlines():
                            logging.error("[stderr] %s", e_line)
                        chk = params.get("backup_image_on_check_error", "no")
                        if chk == "yes":
                            self.backup_image(params, root_dir, "backup", False)
                        raise virt_vm.VMImageCheckError(image_filename)
                    # Leaked clusters, they are known to be harmless to data
                    # integrity
                    elif cmd_result.exit_status == 3:
                        raise error.TestWarn("Leaked clusters were noticed"
                                             " during image check. No data "
                                             "integrity problem was found "
                                             "though.")
 
                    # Just handle normal operation
                    if params.get("backup_image", "no") == "yes":
                        self.backup_image(params, root_dir, "backup", True)
 
            else:
                if not os.path.exists(image_filename):
                    logging.debug("Image file %s not found, skipping check",
                                  image_filename)
                elif not image_is_qcow2:
                    logging.debug("Image file %s not qcow2, skipping check",
                                  image_filename)


