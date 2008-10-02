# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Kernel class

        Kernel: an os kernel
"""

import os, os.path, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import kernel, utils


class DEBKernel(kernel.Kernel):
    """
    This class represents a .deb pre-built kernel.

    It is used to obtain a built kernel and install it on a Host.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """
    def __init__(self):
        super(DEBKernel, self).__init__()


    def install(self, host, **kwargs):
        """
        Install a kernel on the remote host.

        This will also invoke the guest's bootloader to set this
        kernel as the default kernel.

        Args:
                host: the host on which to install the kernel
                [kwargs]: remaining keyword arguments will be passed
                        to Bootloader.add_kernel()

        Raises:
                AutoservError: no package has yet been obtained. Call
                        DEBKernel.get() with a .deb package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be "
                                      "specified via get()")

        remote_tmpdir = host.get_tmp_dir()
        basename = os.path.basename(self.source_material)
        remote_filename = os.path.join(remote_tmpdir, basename)
        host.send_file(self.source_material, remote_filename)
        host.run('dpkg -i "%s"' % (utils.sh_escape(remote_filename),))
        host.run('mkinitramfs -o "%s" "%s"' % (
                utils.sh_escape(self.get_initrd_name()),
                utils.sh_escape(self.get_version()),))

        host.bootloader.add_kernel(self.get_image_name(),
                initrd=self.get_initrd_name(), **kwargs)


    def get_version(self):
        """Get the version of the kernel to be installed.

        Returns:
                The version string, as would be returned
                by 'make kernelrelease'.

        Raises:
                AutoservError: no package has yet been obtained. Call
                        DEBKernel.get() with a .deb package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be "
                                      "specified via get()")

        retval= utils.run('dpkg-deb -f "%s" version' %
                utils.sh_escape(self.source_material),)
        return retval.stdout.strip()


    def get_image_name(self):
        """Get the name of the kernel image to be installed.

        Returns:
                The full path to the kernel image file as it will be
                installed on the host.

        Raises:
                AutoservError: no package has yet been obtained. Call
                        DEBKernel.get() with a .deb package.
        """
        return "/boot/vmlinuz-%s" % (self.get_version(),)


    def get_initrd_name(self):
        """Get the name of the initrd file to be installed.

        Returns:
                The full path to the initrd file as it will be
                installed on the host. If the package includes no
                initrd file, None is returned

        Raises:
                AutoservError: no package has yet been obtained. Call
                        DEBKernel.get() with a .deb package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be "
                                      "specified via get()")

        return "/boot/initrd.img-%s" % (self.get_version(),)

    def extract(self, host):
        """Extract the kernel package.

        This function is only useful to access the content of the
        package (for example the kernel image) without
        installing it. It is not necessary to run this function to
        install the kernel.

        Args:
                host: the host on which to extract the kernel package.

        Returns:
                The full path to the temporary directory on host where
                the package was extracted.

        Raises:
                AutoservError: no package has yet been obtained. Call
                        DEBKernel.get() with a .deb package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be "
                                      "specified via get()")

        remote_tmpdir = host.get_tmp_dir()
        basename = os.path.basename(self.source_material)
        remote_filename = os.path.join(remote_tmpdir, basename)
        host.send_file(self.source_material, remote_filename)
        content_dir= os.path.join(remote_tmpdir, "contents")
        host.run('dpkg -x "%s" "%s"' % (utils.sh_escape(remote_filename),
                                        utils.sh_escape(content_dir),))

        return content_dir
