#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Kernel class

        Kernel: an os kernel
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import os, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import kernel, utils


class RPMKernel(kernel.Kernel):
    """
    This class represents a .rpm pre-built kernel.

    It is used to obtain a built kernel and install it on a Host.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """
    def __init__(self):
        super(RPMKernel, self).__init__()

    def install(self, host, label='autotest',
                default=False, kernel_args = '', install_vmlinux=True):
        """
        Install a kernel on the remote host.

        This will also invoke the guest's bootloader to set this
        kernel as the default kernel if default=True.

        Args:
                host: the host on which to install the kernel
                [kwargs]: remaining keyword arguments will be passed
                        to Bootloader.add_kernel()

        Raises:
                AutoservError: no package has yet been obtained. Call
                        RPMKernel.get() with a .rpm package.
        """
        if len(label) > 15:
            raise error.AutoservError("label for kernel is too long \
            (> 15 chars): %s" % label)
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be \
            specified via get()")
        rpm = self.source_material

        remote_tmpdir = host.get_tmp_dir()
        remote_rpm = os.path.join(remote_tmpdir, os.path.basename(rpm))
        rpm_package = utils.run('/usr/bin/rpm -q -p %s' % rpm).stdout
        vmlinuz = self.get_image_name()
        host.send_file(rpm, remote_rpm)
        host.run('rpm -e ' + rpm_package, ignore_status = True)
        host.run('rpm --force -i ' + remote_rpm)

        # Copy over the uncompressed image if there is one
        if install_vmlinux:
            vmlinux = self.get_vmlinux_name()
            host.run('cd /;rpm2cpio %s | cpio -imuv .%s'
                    % (remote_rpm, vmlinux))
            host.run('ls ' + vmlinux) # Verify

        host.bootloader.remove_kernel(label)
        host.bootloader.add_kernel(vmlinuz, label,
                                   args=kernel_args, default=default)
        if kernel_args:
            host.bootloader.add_args(label, kernel_args)
        if not default:
            host.bootloader.boot_once(label)


    def get_version(self):
        """Get the version of the kernel to be installed.

        Returns:
                The version string, as would be returned
                by 'make kernelrelease'.

        Raises:
                AutoservError: no package has yet been obtained. Call
                        RPMKernel.get() with a .rpm package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be \
            specified via get()")

        retval = utils.run('rpm -qpi %s | grep Version | awk \'{print($3);}\''
            % utils.sh_escape(self.source_material))
        return retval.stdout.strip()


    def get_image_name(self):
        """Get the name of the kernel image to be installed.

        Returns:
                The full path to the kernel image file as it will be
                installed on the host.

        Raises:
                AutoservError: no package has yet been obtained. Call
                        RPMKernel.get() with a .rpm package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be \
            specified via get()")

        vmlinuz = utils.run('rpm -q -l -p %s | grep /boot/vmlinuz'
            % self.source_material).stdout.strip()
        return vmlinuz


    def get_vmlinux_name(self):
        """Get the name of the kernel image to be installed.

        Returns:
                The full path to the kernel image file as it will be
                installed on the host. It is the uncompressed and
                unstripped version of the kernel that can be used with
                oprofile.

        Raises:
                AutoservError: no package has yet been obtained. Call
                        RPMKernel.get() with a .rpm package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be \
            specified via get()")

        vmlinux = utils.run('rpm -q -l -p %s | grep /boot/vmlinux'
            % self.source_material).stdout.strip()
        return vmlinux


    def get_initrd_name(self):
        """Get the name of the initrd file to be installed.

        Returns:
                The full path to the initrd file as it will be
                installed on the host. If the package includes no
                initrd file, None is returned

        Raises:
                AutoservError: no package has yet been obtained. Call
                        RPMKernel.get() with a .rpm package.
        """
        if self.source_material is None:
            raise error.AutoservError("A kernel must first be \
            specified via get()")

        res = utils.run('rpm -q -l -p %s | grep /boot/initrd'
            % self.source_material, ignore_status=True)
        if res.exit_status:
            return None
        return res.stdout.strip()
