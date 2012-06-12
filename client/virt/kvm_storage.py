"""
Classes and functions to handle block/disk images for KVM.

This exports:
  - two functions for get image/blkdebug filename
  - class for image operates and basic parameters
"""
import logging
import os
import shutil
import re
from autotest.client.shared import error
from autotest.client import utils
import virt_utils
import virt_vm
import virt_storage


class QemuImg(virt_storage.QemuImg):
    """
    KVM class for handling operations of disk/block images.
    """
    def __init__(self, params, root_dir, tag):
        """
        Init the default value for image object.

        @param params: Dictionary containing the test parameters.
        @param root_dir: Base directory for relative filenames.
        @param tag: Image tag defined in parameter images
        """
        virt_storage.QemuImg.__init__(self, params, root_dir, tag)
        self.image_cmd = virt_utils.get_path(root_dir,
                                 params.get("qemu_img_binary","qemu-img"))


    def create(self, params):
        """
        Create an image using qemu_img or dd.

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

        @param params: dictionary containing the test parameters
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

        convert_image_filename = virt_storage.get_image_filename(params_convert,
                                                                 root_dir)

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

        @param params: dictionary containing the test parameters

        @note: params should contain:
            cmd -- qemu-img cmd
            snapshot_img -- the snapshot name
            base_img -- base image name
            base_fmt -- base image format
            snapshot_fmt -- the snapshot format
            mode -- there are two value, "safe" and "unsafe",
                default is "safe"
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
        """
        logging.debug("Removing image file %s", self.image_filename)
        if os.path.exists(self.image_filename):
            os.unlink(self.image_filename)
        else:
            logging.debug("Image file %s not found", self.image_filename)



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
        image_filename = self.image_filename
        logging.debug("Checking image file %s", image_filename)
        qemu_img_cmd = self.image_cmd
        image_is_qcow2 = self.image_format == 'qcow2'
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
