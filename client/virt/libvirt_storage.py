"""
Classes and functions to handle block/disk images for libvirt.

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
    libvirt class for handling operations of disk/block images.
    """
    def __init__(self, params, root_dir, tag):
        """
        Init the default value for image object.

        @param params: Dictionary containing the test parameters.
        @param root_dir: Base directory for relative filenames.
        @param tag: Image tag defined in parameter images.
        """
        virt_storage.QemuImg(params, root_dir, tag)
        # Please init image_cmd for libvirt in this class
        # self.image_cmd =


    def create(self, params):
        """
        Create an image.

        @param params: Dictionary containing the test parameters.

        @note: params should contain:
        """
        raise NotImplementedError


    def convert(self, params, root_dir):
        """
        Convert image

        @param params: A dict
        @param root_dir: dir for save the convert image

        @note: params should contain:
        """
        raise NotImplementedError


    def rebase(self, params):
        """
        Rebase image

        @param params: A dict

        @note: params should contain:
        """
        raise NotImplementedError


    def commit(self):
        """
        Commit image to it's base file
        """
        raise NotImplementedError


    def snapshot_create(self):
        """
        Create a snapshot image.

        @note: params should contain:
        """
        raise NotImplementedError


    def remove(self):
        """
        Remove an image file.

        @note: params should contain:
        """
        raise NotImplementedError


    def check_image(self, params, root_dir):
        """
        Check an image using the appropriate tools for each virt backend.

        @param params: Dictionary containing the test parameters.
        @param root_dir: Base directory for relative filenames.

        @note: params should contain:

        @raise VMImageCheckError: In case qemu-img check fails on the image.
        """
        raise NotImplementedError
