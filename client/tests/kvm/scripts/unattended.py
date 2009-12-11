#!/usr/bin/python
"""
Simple script to setup unattended installs on KVM guests.
"""
# -*- coding: utf-8 -*-
import os, sys, shutil, tempfile, re
import common


class SetupError(Exception):
    """
    Simple wrapper for the builtin Exception class.
    """
    pass


class UnattendedInstall(object):
    """
    Creates a floppy disk image that will contain a config file for unattended
    OS install. Optionally, sets up a PXE install server using qemu built in
    TFTP and DHCP servers to install a particular operating system. The
    parameters to the script are retrieved from environment variables.
    """
    def __init__(self):
        """
        Gets params from environment variables and sets class attributes.
        """
        script_dir = os.path.dirname(sys.modules[__name__].__file__)
        kvm_test_dir = os.path.abspath(os.path.join(script_dir, ".."))
        images_dir = os.path.join(kvm_test_dir, 'images')
        self.deps_dir = os.path.join(kvm_test_dir, 'deps')
        self.unattended_dir = os.path.join(kvm_test_dir, 'unattended')

        try:
            tftp_root = os.environ['KVM_TEST_tftp']
            self.tftp_root = os.path.join(kvm_test_dir, tftp_root)
            if not os.path.isdir(self.tftp_root):
                os.makedirs(self.tftp_root)
        except KeyError:
            self.tftp_root = ''

        try:
            self.kernel_args = os.environ['KVM_TEST_kernel_args']
        except KeyError:
            self.kernel_args = ''

        try:
            self.finish_program= os.environ['KVM_TEST_finish_program']
        except:
            self.finish_program = None


        cdrom_iso = os.environ['KVM_TEST_cdrom']
        self.unattended_file = os.environ['KVM_TEST_unattended_file']

        self.qemu_img_bin = os.environ['KVM_TEST_qemu_img_binary']
        self.cdrom_iso = os.path.join(kvm_test_dir, cdrom_iso)
        self.floppy_mount = tempfile.mkdtemp(prefix='floppy_', dir='/tmp')
        self.cdrom_mount = tempfile.mkdtemp(prefix='cdrom_', dir='/tmp')
        self.floppy_img = os.path.join(images_dir, 'floppy.img')


    def create_boot_floppy(self):
        """
        Prepares a boot floppy by creating a floppy image file, mounting it and
        copying an answer file (kickstarts for RH based distros, answer files
        for windows) to it. After that the image is umounted.
        """
        print "Creating boot floppy"

        if os.path.exists(self.floppy_img):
            os.remove(self.floppy_img)

        c_cmd = '%s create -f raw %s 1440k' % (self.qemu_img_bin, self.floppy_img)
        if os.system(c_cmd):
            raise SetupError('Could not create floppy image.')

        f_cmd = 'mkfs.msdos -s 1 %s' % self.floppy_img
        if os.system(f_cmd):
            raise SetupError('Error formatting floppy image.')

        m_cmd = 'mount -o loop %s %s' % (self.floppy_img, self.floppy_mount)
        if os.system(m_cmd):
            raise SetupError('Could not mount floppy image.')

        if self.unattended_file.endswith('.sif'):
            dest_fname = 'winnt.sif'
            setup_file = 'winnt.bat'
            setup_file_path = os.path.join(self.unattended_dir, setup_file)
            setup_file_dest = os.path.join(self.floppy_mount, setup_file)
            shutil.copyfile(setup_file_path, setup_file_dest)
        elif self.unattended_file.endswith('.ks'):
            dest_fname = 'ks.cfg'

        dest = os.path.join(self.floppy_mount, dest_fname)
        shutil.copyfile(self.unattended_file, dest)

        if self.finish_program:
            dest_fname = os.path.basename(self.finish_program)
            dest = os.path.join(self.floppy_mount, dest_fname)
            shutil.copyfile(self.finish_program, dest)

        u_cmd = 'umount %s' % self.floppy_mount
        if os.system(u_cmd):
            raise SetupError('Could not unmount floppy at %s.' %
                             self.floppy_mount)

        os.chmod(self.floppy_img, 0755)

        print "Boot floppy created successfuly"


    def setup_pxe_boot(self):
        """
        Sets up a PXE boot environment using the built in qemu TFTP server.
        Copies the PXE Linux bootloader pxelinux.0 from the host (needs the
        pxelinux package or equivalent for your distro), and vmlinuz and
        initrd.img files from the CD to a directory that qemu will serve trough
        TFTP to the VM.
        """
        print "Setting up PXE boot using TFTP root %s" % self.tftp_root

        pxe_file = None
        pxe_paths = ['/usr/lib/syslinux/pxelinux.0',
                     '/usr/share/syslinux/pxelinux.0']
        for path in pxe_paths:
            if os.path.isfile(path):
                pxe_file = path
                break

        if not pxe_file:
            raise SetupError('Cannot find PXE boot loader pxelinux.0. Make '
                             'sure pxelinux or equivalent package for your '
                             'distro is installed.')

        pxe_dest = os.path.join(self.tftp_root, 'pxelinux.0')
        shutil.copyfile(pxe_file, pxe_dest)

        m_cmd = 'mount -t iso9660 -v -o loop,ro %s %s' % (self.cdrom_iso,
                                                          self.cdrom_mount)
        if os.system(m_cmd):
            raise SetupError('Could not mount CD image %s.' % self.cdrom_iso)

        p = os.path.join('images', 'pxeboot')
        pxe_dir = os.path.join(self.cdrom_mount, p)
        pxe_image = os.path.join(pxe_dir, 'vmlinuz')
        pxe_initrd = os.path.join(pxe_dir, 'initrd.img')

        if not os.path.isdir(pxe_dir):
            raise SetupError('The ISO image does not have a %s dir. The script '
                             'assumes that the cd has a %s dir where to search '
                             'for the vmlinuz image.' % (p, p))

        if not os.path.isfile(pxe_image) or not os.path.isfile(pxe_initrd):
            raise SetupError('The location %s is lacking either a vmlinuz or a '
                             'initrd.img file. Cannot find a PXE image to '
                             'proceed.' % pxe_dir)

        tftp_image = os.path.join(self.tftp_root, 'vmlinuz')
        tftp_initrd = os.path.join(self.tftp_root, 'initrd.img')
        shutil.copyfile(pxe_image, tftp_image)
        shutil.copyfile(pxe_initrd, tftp_initrd)

        u_cmd = 'umount %s' % self.cdrom_mount
        if os.system(u_cmd):
            raise SetupError('Could not unmount CD at %s.' % self.cdrom_mount)

        pxe_config_dir = os.path.join(self.tftp_root, 'pxelinux.cfg')
        if not os.path.isdir(pxe_config_dir):
            os.makedirs(pxe_config_dir)
        pxe_config_path = os.path.join(pxe_config_dir, 'default')

        pxe_config = open(pxe_config_path, 'w')
        pxe_config.write('DEFAULT pxeboot\n')
        pxe_config.write('TIMEOUT 20\n')
        pxe_config.write('PROMPT 0\n')
        pxe_config.write('LABEL pxeboot\n')
        pxe_config.write('     KERNEL vmlinuz\n')
        pxe_config.write('     KERNEL vmlinuz\n')
        pxe_config.write('     APPEND initrd=initrd.img %s\n' %
                         self.kernel_args)
        pxe_config.close()

        print "PXE boot successfuly set"

    def cleanup(self):
        """
        Clean up previously used mount points.
        """
        print "Cleaning up unused mount points"
        for mount in [self.floppy_mount, self.cdrom_mount]:
            if os.path.isdir(mount):
                if os.path.ismount(mount):
                    print "Path %s is still mounted, please verify" % mount
                else:
                    print "Removing mount point %s" % mount
                    os.rmdir(mount)


    def setup(self):
        print "Starting unattended install setup"

        print "Variables set:"
        print "    qemu_img_bin: " + str(self.qemu_img_bin)
        print "    cdrom iso: " + str(self.cdrom_iso)
        print "    unattended_file: " + str(self.unattended_file)
        print "    kernel_args: " + str(self.kernel_args)
        print "    tftp_root: " + str(self.tftp_root)
        print "    floppy_mount: " + str(self.floppy_mount)
        print "    floppy_img: " + str(self.floppy_img)
        print "    finish_program: " + str(self.finish_program)

        self.create_boot_floppy()
        if self.tftp_root:
            self.setup_pxe_boot()
        self.cleanup()
        print "Unattended install setup finished successfuly"


if __name__ == "__main__":
    os_install = UnattendedInstall()
    os_install.setup()
