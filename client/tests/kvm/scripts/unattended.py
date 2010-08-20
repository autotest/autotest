#!/usr/bin/python
"""
Simple script to setup unattended installs on KVM guests.
"""
# -*- coding: utf-8 -*-
import os, sys, shutil, tempfile, re, ConfigParser, glob
import common

KNOWN_PACKAGE_MANAGERS = ['rpm', 'dpkg']


def command(cmd):
    """
    Find a given command on the user's PATH.

    @param cmd: Command you wish to find (ie, 'ls').
    @return: Full path to the command.
    @raise ValueError: In case the command are not found on PATH.
    """
    for dir in os.environ['PATH'].split(':'):
        file = os.path.join(dir, cmd)
        if os.path.exists(file):
            return file
    raise ValueError('Missing command: %s' % cmd)


def package_that_owns(file):
    """
    Inquiry the main package manager which package owns file.

    @param file: Path to a given file
    """
    support_info = {}
    for package_manager in KNOWN_PACKAGE_MANAGERS:
        try:
            command(package_manager)
            support_info[package_manager] = True
        except:
            support_info[package_manager] = False

    if support_info['rpm']:
        return str(os.popen('rpm -qf %s' % file).read())
    elif support_info['dpkg']:
        return str(os.popen('dpkg -S %s' % file).read())
    else:
        return ('Did not find a known package manager to inquire about '
                'file %s' % file)


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

        tftp_root = os.environ.get('KVM_TEST_tftp', '')
        if tftp_root:
            self.tftp_root = os.path.join(kvm_test_dir, tftp_root)
            if not os.path.isdir(self.tftp_root):
                os.makedirs(self.tftp_root)
        else:
            self.tftp_root = tftp_root

        self.kernel_args = os.environ.get('KVM_TEST_kernel_args', '')
        self.finish_program = os.environ.get('KVM_TEST_finish_program', '')
        cdrom_iso = os.environ.get('KVM_TEST_cdrom_cd1')
        self.unattended_file = os.environ.get('KVM_TEST_unattended_file')

        install_virtio = os.environ.get('KVM_TEST_install_virtio', 'no')
        if install_virtio == 'yes':
            self.install_virtio = True
        else:
            self.install_virtio = False

        virtio_floppy = os.environ.get('KVM_TEST_virtio_floppy', '')
        self.virtio_floppy = None
        self.virtio_floppy_mount = tempfile.mkdtemp(prefix='floppy_',
                                                    dir='/tmp')
        if self.install_virtio:
            if virtio_floppy and os.path.isfile(virtio_floppy):
                print package_that_owns(virtio_floppy)
                self.virtio_floppy = virtio_floppy
            elif virtio_floppy and not os.path.isfile(virtio_floppy):
                print ('Virtio floppy path %s was not found. Please verify' %
                       virtio_floppy)

        vni = os.environ.get('KVM_TEST_virtio_network_installer', '')
        self.virtio_network_installer = None
        if self.install_virtio and vni:
            self.virtio_network_installer = vni

        voi = os.environ.get('KVM_TEST_virtio_oemsetup_id', '')
        self.virtio_oemsetup_identifier = None
        if self.install_virtio and voi:
            self.virtio_oemsetup_identifier = voi

        vsp = os.environ.get('KVM_TEST_virtio_storage_path', '')
        self.virtio_storage_path = None
        if self.install_virtio and vsp:
            self.virtio_storage_path = vsp

        self.qemu_img_bin = os.environ.get('KVM_TEST_qemu_img_binary')
        if not os.path.isabs(self.qemu_img_bin):
            self.qemu_img_bin = os.path.join(kvm_test_dir, self.qemu_img_bin)
        self.cdrom_iso = os.path.join(kvm_test_dir, cdrom_iso)
        self.floppy_mount = tempfile.mkdtemp(prefix='floppy_', dir='/tmp')
        self.cdrom_mount = tempfile.mkdtemp(prefix='cdrom_', dir='/tmp')
        self.nfs_mount = tempfile.mkdtemp(prefix='nfs_', dir='/tmp')
        floppy_name = os.environ['KVM_TEST_floppy']
        self.floppy_img = os.path.join(kvm_test_dir, floppy_name)
        floppy_dir = os.path.dirname(self.floppy_img)
        if not os.path.isdir(floppy_dir):
            os.makedirs(floppy_dir)

        self.pxe_dir = os.environ.get('KVM_TEST_pxe_dir', '')
        self.pxe_image = os.environ.get('KVM_TEST_pxe_image', '')
        self.pxe_initrd = os.environ.get('KVM_TEST_pxe_initrd', '')

        self.medium = os.environ.get('KVM_TEST_medium', '')
        self.url = os.environ.get('KVM_TEST_url', '')
        self.kernel = os.environ.get('KVM_TEST_kernel', '')
        self.initrd = os.environ.get('KVM_TEST_initrd', '')
        self.nfs_server = os.environ.get('KVM_TEST_nfs_server', '')
        self.nfs_dir = os.environ.get('KVM_TEST_nfs_dir', '')
        self.image_path = kvm_test_dir
        self.kernel_path = os.path.join(self.image_path, self.kernel)
        self.initrd_path = os.path.join(self.image_path, self.initrd)


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

        if os.path.exists(self.floppy_img):
            os.remove(self.floppy_img)

        c_cmd = '%s create -f raw %s 1440k' % (self.qemu_img_bin,
                                               self.floppy_img)
        if os.system(c_cmd):
            raise SetupError('Could not create floppy image.')

        f_cmd = 'mkfs.msdos -s 1 %s' % self.floppy_img
        if os.system(f_cmd):
            raise SetupError('Error formatting floppy image.')

        try:
            m_cmd = 'mount -o loop,rw %s %s' % (self.floppy_img,
                                                self.floppy_mount)
            if os.system(m_cmd):
                raise SetupError('Could not mount floppy image.')

            if self.unattended_file.endswith('.sif'):
                dest_fname = 'winnt.sif'
                setup_file = 'winnt.bat'
                setup_file_path = os.path.join(self.unattended_dir, setup_file)
                setup_file_dest = os.path.join(self.floppy_mount, setup_file)
                shutil.copyfile(setup_file_path, setup_file_dest)
                if self.install_virtio:
                    self.setup_virtio_win2003()

            elif self.unattended_file.endswith('.ks'):
                # Red Hat kickstart install
                dest_fname = 'ks.cfg'
            elif self.unattended_file.endswith('.xml'):
                if  self.tftp_root is '':
                    # Windows unattended install
                    dest_fname = "autounattend.xml"
                    if self.install_virtio:
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
                content = "nfs --server=%s --dir=%s" % (self.nfs_server, self.nfs_dir)
            else:
                raise SetupError("Unexpected installation medium %s" % self.url)

            unattended_contents = re.sub(dummy_medium_re, content, unattended_contents)

            dummy_path = "C:"

            dummy_storage_re = r'\bKVM_TEST_STORAGE_DRIVER_PATH\b'
            storage_driver = os.environ.get('KVM_TEST_virtio_storage_path', '')
            if re.search(dummy_storage_re, unattended_contents):
                if self.install_virtio:
                    unattended_contents = re.sub(dummy_storage_re,
                                                 storage_driver,
                                                 unattended_contents)
                else:
                    unattended_contents = re.sub(dummy_storage_re,
                                                 dummy_path,
                                                 unattended_contents)

            dummy_network_re = r'\bKVM_TEST_NETWORK_DRIVER_PATH\b'
            network_driver = os.environ.get('KVM_TEST_virtio_network_path', '')
            if re.search(dummy_network_re, unattended_contents):
                if self.install_virtio:
                    unattended_contents = re.sub(dummy_network_re,
                                                 network_driver,
                                                 unattended_contents)
                else:
                    unattended_contents = re.sub(dummy_network_re,
                                                 dummy_path,
                                                 unattended_contents)

            dummy_nw_install_re = r'\bKVM_TEST_VIRTIO_NETWORK_INSTALLER\b'
            nw_install = os.environ.get('KVM_TEST_virtio_network_installer',
                                        'help')
            if re.search(dummy_nw_install_re, unattended_contents):
                if self.install_virtio:
                    unattended_contents = re.sub(dummy_nw_install_re,
                                                 nw_install,
                                                 unattended_contents)
                else:
                    unattended_contents = re.sub(dummy_nw_install_re,
                                                 'help',
                                                 unattended_contents)

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

        try:
            m_cmd = 'mount -t iso9660 -v -o loop,ro %s %s' % (self.cdrom_iso,
                                                              self.cdrom_mount)
            if os.system(m_cmd):
                raise SetupError('Could not mount CD image %s.' %
                                 self.cdrom_iso)

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

            tftp_image = os.path.join(self.tftp_root, 'vmlinuz')
            tftp_initrd = os.path.join(self.tftp_root, 'initrd.img')
            shutil.copyfile(pxe_image, tftp_image)
            shutil.copyfile(pxe_initrd, tftp_initrd)

        finally:
            u_cmd = 'umount %s' % self.cdrom_mount
            if os.system(u_cmd):
                raise SetupError('Could not unmount CD at %s.' %
                                 self.cdrom_mount)
            self.cleanup(self.cdrom_mount)

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

        m_cmd = "mount %s:%s %s -o ro" % (self.nfs_server, self.nfs_dir, self.nfs_mount)
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

        print "Variables set:"
        print "    medium: " + str(self.medium)
        print "    qemu_img_bin: " + str(self.qemu_img_bin)
        print "    cdrom iso: " + str(self.cdrom_iso)
        print "    unattended_file: " + str(self.unattended_file)
        print "    kernel_args: " + str(self.kernel_args)
        print "    tftp_root: " + str(self.tftp_root)
        print "    floppy_mount: " + str(self.floppy_mount)
        print "    floppy_img: " + str(self.floppy_img)
        print "    finish_program: " + str(self.finish_program)
        print "    pxe_dir: " + str(self.pxe_dir)
        print "    pxe_image: " + str(self.pxe_image)
        print "    pxe_initrd: " + str(self.pxe_initrd)
        print "    url: " + str(self.url)
        print "    kernel: " + str(self.kernel)
        print "    initrd: " + str(self.initrd)
        print "    nfs_server: " + str(self.nfs_server)
        print "    nfs_dir: " + str(self.nfs_dir)
        print "    nfs_mount: " + str(self.nfs_mount)

        if self.unattended_file and self.floppy_img is not None:
            self.create_boot_floppy()
        if self.medium == "cdrom":
            if self.tftp_root:
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
