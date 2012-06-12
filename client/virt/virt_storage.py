"""
Classes and functions to handle storage devices.

This exports:
  - two functions for get image/blkdebug filename
  - class for image operates and basic parameters
"""
import logging, os, shutil, re
from autotest.client import utils
import virt_utils, virt_vm


def preprocess_images(bindir, params, env):
    # Clone master image form vms.
    for vm_name in params.get("vms").split():
        vm = env.get_vm(vm_name)
        if vm:
            vm.destroy(free_mac_addresses=False)
        vm_params = params.object_params(vm_name)
        for image in vm_params.get("master_images_clone").split():
            image_obj = QemuImg(params, bindir, image)
            image_obj.clone_image(params, vm_name, image, bindir)


def postprocess_images(bindir, params):
    for vm in params.get("vms").split():
        vm_params = params.object_params(vm)
        for image in vm_params.get("master_images_clone").split():
            image_obj = QemuImg(params, bindir, image)
            image_obj.rm_cloned_image(params, vm, image, bindir)


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
    Option not found in the odbject
    """
    def __init__(self, option):
        self.option = option


    def __str__(self):
        return "%s is missing. Please check your parameters" % self.option


class QemuImg(object):
    """
    A basic class for handling operations of disk/block images.
    """
    def __init__(self, params, root_dir, tag):
        """
        Init the default value for image object.

        @param params: Dictionary containing the test parameters.
        @param root_dir: Base directory for relative filenames.
        @param tag: Image tag defined in parameter images.
        """
        self.image_filename = get_image_filename(params, root_dir)
        self.image_format = params.get("image_format", "qcow2")
        self.size = params.get("image_size", "10G")
        self.check_output = params.get("check_output") == "yes"
        self.image_blkdebug_filename = get_image_blkdebug_filename(params,
                                                                   root_dir)
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

        @param option: option should be checked
        """
        if option not in self.__dict__:
            raise OptionMissing(option)


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
