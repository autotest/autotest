#!/usr/bin/python
"""
Simple script to setup unattended installs on KVM guests.
"""
# -*- coding: utf-8 -*-
import os, sys, shutil, tempfile, re, ConfigParser, glob, inspect
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

        attributes = ['kernel_args', 'finish_program', 'cdrom_cd1',
                      'unattended_file', 'medium', 'url', 'kernel', 'initrd',
                      'nfs_server', 'nfs_dir', 'pxe_dir', 'pxe_image',
                      'pxe_initrd', 'install_virtio', 'tftp', 'qemu_img_binary',
                      'floppy']
        for a in attributes:
            self._setattr(a)

        if self.install_virtio == 'yes':
            v_attributes = ['virtio_floppy', 'virtio_storage_path',
                            'virtio_network_path', 'virtio_oemsetup_id',
                            'virtio_network_installer']
            for va in v_attributes:
                self._setattr(va)
            self.virtio_floppy_mount = tempfile.mkdtemp(prefix='virtio_floppy_',
                                                        dir='/tmp')

        if self.tftp:
            self.tftp = os.path.join(kvm_test_dir, self.tftp)
            if not os.path.isdir(self.tftp):
                os.makedirs(self.tftp)

        if not os.path.isabs(self.qemu_img_binary):
            self.qemu_img_binary = os.path.join(kvm_test_dir,
                                                self.qemu_img_binary)

        self.cdrom_cd1 = os.path.join(kvm_test_dir, self.cdrom_cd1)
        self.floppy_mount = tempfile.mkdtemp(prefix='floppy_', dir='/tmp')
        self.cdrom_mount = tempfile.mkdtemp(prefix='cdrom_', dir='/tmp')
        if self.medium == 'nfs':
            self.nfs_mount = tempfile.mkdtemp(prefix='nfs_', dir='/tmp')

        self.floppy = os.path.join(kvm_test_dir, self.floppy)
        if not os.path.isdir(os.path.dirname(self.floppy)):
            os.makedirs(os.path.dirname(self.floppy))

        self.image_path = kvm_test_dir
        self.kernel_path = os.path.join(self.image_path, self.kernel)
        self.initrd_path = os.path.join(self.image_path, self.initrd)


    def _setattr(self, key):
        """
        Populate class attributes with contents of environment variables.

        Example: KVM_TEST_medium will populate self.medium.

        @param key: Name of the class attribute we desire to have.
        """
        env_name = 'KVM_TEST_%s' % key
        value = os.environ.get(env_name, '')
        setattr(self, key, value)


    def copy_virtio_drivers_floppy(self):
        """
        Copy the virtio drivers on the virtio floppy to the install floppy.

        1) Mount the floppy containing the viostor drivers
        2) Copy its contents to the root of the install floppy
        """
        m_cmd = 'mount -o loop %s %s' % (self.virtio_floppy,
                                         self.virtio_floppy_mount)
        pwd = os.getcwd()
        try:
            if os.system(m_cmd):
                raise SetupError('Could not mount virtio floppy driver')
            os.chdir(self.virtio_floppy_mount)
            path_list = glob.glob('*')
            for path in path_list:
                src = os.path.join(self.virtio_floppy_mount, path)
                dst = os.path.join(self.floppy_mount, path)
                if os.path.isdir(path):
                    shutil.copytree(src, dst)
                elif os.path.isfile(path):
                    shutil.copyfile(src, dst)
        finally:
            os.chdir(pwd)
            u_cmd = 'umount %s' % self.virtio_floppy_mount
            if os.system(u_cmd):
                raise SetupError('Could not unmount virtio floppy at %s' %
                                 self.virtio_floppy_mount)
            self.cleanup(self.virtio_floppy_mount)


    def setup_virtio_win2008(self):
        """
        Setup the install floppy with the virtio storage drivers, win2008 style.

        Win2008, Vista and 7 require people to point out the path to the drivers
        on the unattended file, so we just need to copy the drivers to the
        driver floppy disk.
        Process:

        1) Copy the virtio drivers on the virtio floppy to the install floppy
        """
        self.copy_virtio_drivers_floppy()


    def setup_virtio_win2003(self):
        """
        Setup the install floppy with the virtio storage drivers, win2003 style.

        Win2003 and WinXP depend on the file txtsetup.oem file to install
        the virtio drivers from the floppy, which is a .ini file.
        Process:

        1) Copy the virtio drivers on the virtio floppy to the install floppy
        2) Parse the ini file with config parser
        3) Modify the identifier of the default session that is going to be
           executed on the config parser object
        4) Re-write the config file to the disk
        """
        self.copy_virtio_drivers_floppy()
        txtsetup_oem = os.path.join(self.floppy_mount, 'txtsetup.oem')
        if not os.path.isfile(txtsetup_oem):
            raise SetupError('File txtsetup.oem not found on the install '
                             'floppy. Please verify if your floppy virtio '
                             'driver image has this file')
        parser = ConfigParser.ConfigParser()
        parser.read(txtsetup_oem)
        if not parser.has_section('Defaults'):
            raise SetupError('File txtsetup.oem does not have the session '
                             '"Defaults". Please check txtsetup.oem')
        default_driver = parser.get('Defaults', 'SCSI')
        if default_driver != self.virtio_oemsetup_identifier:
            parser.set('Defaults', 'SCSI', self.virtio_oemsetup_identifier)
            fp = open(txtsetup_oem, 'w')
            parser.write(fp)
            fp.close()


    def create_boot_floppy(self):
        """
        Prepares a boot floppy by creating a floppy image file, mounting it and
        copying an answer file (kickstarts for RH based distros, answer files
        for windows) to it. After that the image is umounted.
        """
        print "Creating boot floppy"

        if os.path.exists(self.floppy):
            os.remove(self.floppy)

        c_cmd = '%s create -f raw %s 1440k' % (self.qemu_img_binary,
                                               self.floppy)
        if os.system(c_cmd):
            raise SetupError('Could not create floppy image.')

        f_cmd = 'mkfs.msdos -s 1 %s' % self.floppy
        if os.system(f_cmd):
            raise SetupError('Error formatting floppy image.')

        try:
            m_cmd = 'mount -o loop,rw %s %s' % (self.floppy,
                                                self.floppy_mount)
            if os.system(m_cmd):
                raise SetupError('Could not mount floppy image.')

            if self.unattended_file.endswith('.sif'):
                dest_fname = 'winnt.sif'
                setup_file = 'winnt.bat'
                setup_file_path = os.path.join(self.unattended_dir, setup_file)
                setup_file_dest = os.path.join(self.floppy_mount, setup_file)
                shutil.copyfile(setup_file_path, setup_file_dest)
                if self.install_virtio == "yes":
                    self.setup_virtio_win2003()

            elif self.unattended_file.endswith('.ks'):
                # Red Hat kickstart install
                dest_fname = 'ks.cfg'
            elif self.unattended_file.endswith('.xml'):
                if not self.tftp:
                    # Windows unattended install
                    dest_fname = "autounattend.xml"
                    if self.install_virtio == "yes":
                        self.setup_virtio_win2008()
                else:
                    # SUSE autoyast install
                    dest_fname = "autoinst.xml"

            dest = os.path.join(self.floppy_mount, dest_fname)

            # Replace KVM_TEST_CDKEY (in the unattended file) with the cdkey
            # provided for this test and replace the KVM_TEST_MEDIUM with
            # the tree url or nfs address provided for this test.
            unattended_contents = open(self.unattended_file).read()
            dummy_cdkey_re = r'\bKVM_TEST_CDKEY\b'
            real_cdkey = os.environ.get('KVM_TEST_cdkey')
            if re.search(dummy_cdkey_re, unattended_contents):
                if real_cdkey:
                    unattended_contents = re.sub(dummy_cdkey_re, real_cdkey,
                                                 unattended_contents)
                else:
                    print ("WARNING: 'cdkey' required but not specified for "
                           "this unattended installation")

            dummy_medium_re = r'\bKVM_TEST_MEDIUM\b'
            if self.medium == "cdrom":
                content = "cdrom"
            elif self.medium == "url":
                content = "url --url %s" % self.url
            elif self.medium == "nfs":
                content = "nfs --server=%s --dir=%s" % (self.nfs_server,
                                                        self.nfs_dir)
            else:
                raise SetupError("Unexpected installation medium %s" % self.url)

            unattended_contents = re.sub(dummy_medium_re, content,
                                         unattended_contents)

            def replace_virtio_key(contents, dummy_re, env):
                """
                Replace a virtio dummy string with contents.

                If install_virtio is not set, replace it with a dummy string.

                @param contents: Contents of the unattended file
                @param dummy_re: Regular expression used to search on the.
                        unattended file contents.
                @param env: Name of the environment variable.
                """
                dummy_path = "C:"
                driver = os.environ.get(env, '')

                if re.search(dummy_re, contents):
                    if self.install_virtio == "yes":
                        if driver.endswith("msi"):
                            driver = 'msiexec /passive /package ' + driver
                        else:
                            try:
                                # Let's escape windows style paths properly
                                drive, path = driver.split(":")
                                driver = drive + ":" + re.escape(path)
                            except:
                                pass
                        contents = re.sub(dummy_re, driver, contents)
                    else:
                        contents = re.sub(dummy_re, dummy_path, contents)
                return contents

            vdict = {r'\bKVM_TEST_STORAGE_DRIVER_PATH\b':
                     'KVM_TEST_virtio_storage_path',
                     r'\bKVM_TEST_NETWORK_DRIVER_PATH\b':
                     'KVM_TEST_virtio_network_path',
                     r'\bKVM_TEST_VIRTIO_NETWORK_INSTALLER\b':
                     'KVM_TEST_virtio_network_installer_path'}

            for vkey in vdict:
                unattended_contents = replace_virtio_key(unattended_contents,
                                                         vkey, vdict[vkey])

            print
            print "Unattended install %s contents:" % dest_fname
            print unattended_contents
            # Write the unattended file contents to 'dest'
            open(dest, 'w').write(unattended_contents)

            if self.finish_program:
                dest_fname = os.path.basename(self.finish_program)
                dest = os.path.join(self.floppy_mount, dest_fname)
                shutil.copyfile(self.finish_program, dest)

        finally:
            u_cmd = 'umount %s' % self.floppy_mount
            if os.system(u_cmd):
                raise SetupError('Could not unmount floppy at %s.' %
                                 self.floppy_mount)
            self.cleanup(self.floppy_mount)

        os.chmod(self.floppy, 0755)

        print "Boot floppy created successfuly"


    def setup_pxe_boot(self):
        """
        Sets up a PXE boot environment using the built in qemu TFTP server.
        Copies the PXE Linux bootloader pxelinux.0 from the host (needs the
        pxelinux package or equivalent for your distro), and vmlinuz and
        initrd.img files from the CD to a directory that qemu will serve trough
        TFTP to the VM.
        """
        print "Setting up PXE boot using TFTP root %s" % self.tftp

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

        pxe_dest = os.path.join(self.tftp, 'pxelinux.0')
        shutil.copyfile(pxe_file, pxe_dest)

        try:
            m_cmd = 'mount -t iso9660 -v -o loop,ro %s %s' % (self.cdrom_cd1,
                                                              self.cdrom_mount)
            if os.system(m_cmd):
                raise SetupError('Could not mount CD image %s.' %
                                 self.cdrom_cd1)

            pxe_dir = os.path.join(self.cdrom_mount, self.pxe_dir)
            pxe_image = os.path.join(pxe_dir, self.pxe_image)
            pxe_initrd = os.path.join(pxe_dir, self.pxe_initrd)

            if not os.path.isdir(pxe_dir):
                raise SetupError('The ISO image does not have a %s dir. The '
                                 'script assumes that the cd has a %s dir '
                                 'where to search for the vmlinuz image.' %
                                 (self.pxe_dir, self.pxe_dir))

            if not os.path.isfile(pxe_image) or not os.path.isfile(pxe_initrd):
                raise SetupError('The location %s is lacking either a vmlinuz '
                                 'or a initrd.img file. Cannot find a PXE '
                                 'image to proceed.' % self.pxe_dir)

            tftp_image = os.path.join(self.tftp, 'vmlinuz')
            tftp_initrd = os.path.join(self.tftp, 'initrd.img')
            shutil.copyfile(pxe_image, tftp_image)
            shutil.copyfile(pxe_initrd, tftp_initrd)

        finally:
            u_cmd = 'umount %s' % self.cdrom_mount
            if os.system(u_cmd):
                raise SetupError('Could not unmount CD at %s.' %
                                 self.cdrom_mount)
            self.cleanup(self.cdrom_mount)

        pxe_config_dir = os.path.join(self.tftp, 'pxelinux.cfg')
        if not os.path.isdir(pxe_config_dir):
            os.makedirs(pxe_config_dir)
        pxe_config_path = os.path.join(pxe_config_dir, 'default')

        pxe_config = open(pxe_config_path, 'w')
        pxe_config.write('DEFAULT pxeboot\n')
        pxe_config.write('TIMEOUT 20\n')
        pxe_config.write('PROMPT 0\n')
        pxe_config.write('LABEL pxeboot\n')
        pxe_config.write('     KERNEL vmlinuz\n')
        pxe_config.write('     APPEND initrd=initrd.img %s\n' %
                         self.kernel_args)
        pxe_config.close()

        print "PXE boot successfuly set"


    def setup_url(self):
        """
        Download the vmlinuz and initrd.img from URL
        """
        print "Downloading the vmlinuz and initrd.img"
        os.chdir(self.image_path)

        kernel_fetch_cmd = "wget -q %s/isolinux/%s" % (self.url, self.kernel)
        initrd_fetch_cmd = "wget -q %s/isolinux/%s" % (self.url, self.initrd)

        if os.path.exists(self.kernel):
            os.unlink(self.kernel)
        if os.path.exists(self.initrd):
            os.unlink(self.initrd)

        if os.system(kernel_fetch_cmd) != 0:
            raise SetupError("Could not fetch vmlinuz from %s" % self.url)
        if os.system(initrd_fetch_cmd) != 0:
            raise SetupError("Could not fetch initrd.img from %s" % self.url)

        print "Downloading finish"


    def setup_nfs(self):
        """
        Copy the vmlinuz and initrd.img from nfs.
        """
        print "Copying the vmlinuz and initrd.img from nfs"

        m_cmd = "mount %s:%s %s -o ro" % (self.nfs_server, self.nfs_dir,
                                          self.nfs_mount)
        if os.system(m_cmd):
            raise SetupError('Could not mount nfs server.')

        kernel_fetch_cmd = "cp %s/isolinux/%s %s" % (self.nfs_mount,
                                                     self.kernel,
                                                     self.image_path)
        initrd_fetch_cmd = "cp %s/isolinux/%s %s" % (self.nfs_mount,
                                                     self.initrd,
                                                     self.image_path)

        try:
            if os.system(kernel_fetch_cmd):
                raise SetupError("Could not copy the vmlinuz from %s" %
                                 self.nfs_mount)
            if os.system(initrd_fetch_cmd):
                raise SetupError("Could not copy the initrd.img from %s" %
                                 self.nfs_mount)
        finally:
            u_cmd = "umount %s" % self.nfs_mount
            if os.system(u_cmd):
                raise SetupError("Could not unmont nfs at %s" % self.nfs_mount)
            self.cleanup(self.nfs_mount)


    def cleanup(self, mount):
        """
        Clean up a previously used mountpoint.

        @param mount: Mountpoint to be cleaned up.
        """
        if os.path.isdir(mount):
            if os.path.ismount(mount):
                print "Path %s is still mounted, please verify" % mount
            else:
                print "Removing mount point %s" % mount
                os.rmdir(mount)


    def setup(self):
        print "Starting unattended install setup"
        print

        print "Variables set:"
        for member in inspect.getmembers(self):
            name, value = member
            attribute = getattr(self, name)
            if not (name.startswith("__") or callable(attribute) or not value):
                print "    %s: %s" % (name, value)
        print

        if self.unattended_file and self.floppy is not None:
            self.create_boot_floppy()
        if self.medium == "cdrom":
            if self.tftp:
                self.setup_pxe_boot()
        elif self.medium == "url":
            self.setup_url()
        elif self.medium == "nfs":
            self.setup_nfs()
        else:
            raise SetupError("Unexpected installation method %s" %
                             self.medium)
        print "Unattended install setup finished successfuly"


if __name__ == "__main__":
    os_install = UnattendedInstall()
    os_install.setup()
