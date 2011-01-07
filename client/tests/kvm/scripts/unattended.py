#!/usr/bin/python
"""
Simple script to setup unattended installs on KVM guests.
"""
# -*- coding: utf-8 -*-
import os, sys, shutil, tempfile, re, ConfigParser, glob, inspect
import common


SCRIPT_DIR = os.path.dirname(sys.modules[__name__].__file__)
KVM_TEST_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


class SetupError(Exception):
    """
    Simple wrapper for the builtin Exception class.
    """
    pass


def find_command(cmd):
    """
    Searches for a command on common paths, error if it can't find it.

    @param cmd: Command to be found.
    """
    if os.path.exists(cmd):
        return cmd
    for dir in ["/usr/local/sbin", "/usr/local/bin",
                "/usr/sbin", "/usr/bin", "/sbin", "/bin"]:
        file = os.path.join(dir, cmd)
        if os.path.exists(file):
            return file
    raise ValueError('Missing command: %s' % cmd)


def run(cmd, info=None):
    """
    Run a command and throw an exception if it fails.
    Optionally, you can provide additional contextual info.

    @param cmd: Command string.
    @param reason: Optional string that explains the context of the failure.

    @raise: SetupError if command fails.
    """
    print "Running '%s'" % cmd
    cmd_name = cmd.split(' ')[0]
    find_command(cmd_name)
    if os.system(cmd):
        e_msg = 'Command failed: %s' % cmd
        if info is not None:
            e_msg += '. %s' % info
        raise SetupError(e_msg)


def cleanup(dir):
    """
    If dir is a mountpoint, do what is possible to unmount it. Afterwards,
    try to remove it.

    @param dir: Directory to be cleaned up.
    """
    print "Cleaning up directory %s" % dir
    if os.path.ismount(dir):
        os.system('fuser -k %s' % dir)
        run('umount %s' % dir, info='Could not unmount %s' % dir)
    if os.path.isdir(dir):
        shutil.rmtree(dir)


def clean_old_image(image):
    """
    Clean a leftover image file from previous processes. If it contains a
    mounted file system, do the proper cleanup procedures.

    @param image: Path to image to be cleaned up.
    """
    if os.path.exists(image):
        mtab = open('/etc/mtab', 'r')
        mtab_contents = mtab.read()
        mtab.close()
        if image in mtab_contents:
            os.system('fuser -k %s' % image)
            os.system('umount %s' % image)
        os.remove(image)


class Disk(object):
    """
    Abstract class for Disk objects, with the common methods implemented.
    """
    def __init__(self):
        self.path = None


    def setup_answer_file(self, filename, contents):
        answer_file = open(os.path.join(self.mount, filename), 'w')
        answer_file.write(contents)
        answer_file.close()


    def copy_to(self, src):
        dst = os.path.join(self.mount, os.path.basename(src))
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.isfile(src):
            shutil.copyfile(src, dst)


    def close(self):
        os.chmod(self.path, 0755)
        cleanup(self.mount)
        print "Disk %s successfuly set" % self.path


class FloppyDisk(Disk):
    """
    Represents a 1.44 MB floppy disk. We can copy files to it, and setup it in
    convenient ways.
    """
    def __init__(self, path):
        print "Creating floppy unattended image %s" % path
        qemu_img_binary = os.environ['KVM_TEST_qemu_img_binary']
        if not os.path.isabs(qemu_img_binary):
            qemu_img_binary = os.path.join(KVM_TEST_DIR, qemu_img_binary)
        if not os.path.exists(qemu_img_binary):
            raise SetupError('The qemu-img binary that is supposed to be used '
                             '(%s) does not exist. Please verify your '
                             'configuration' % qemu_img_binary)

        self.mount = tempfile.mkdtemp(prefix='floppy_', dir='/tmp')
        self.virtio_mount = None
        self.path = path
        clean_old_image(path)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        try:
            c_cmd = '%s create -f raw %s 1440k' % (qemu_img_binary, path)
            run(c_cmd, info='Could not create floppy image')
            f_cmd = 'mkfs.msdos -s 1 %s' % path
            run(f_cmd, info='Error formatting floppy image')
            m_cmd = 'mount -o loop,rw %s %s' % (path, self.mount)
            run(m_cmd, info='Could not mount floppy image')
        except:
            cleanup(self.mount)


    def _copy_virtio_drivers(self, virtio_floppy):
        """
        Copy the virtio drivers on the virtio floppy to the install floppy.

        1) Mount the floppy containing the viostor drivers
        2) Copy its contents to the root of the install floppy
        """
        virtio_mount = tempfile.mkdtemp(prefix='virtio_floppy_', dir='/tmp')

        pwd = os.getcwd()
        try:
            m_cmd = 'mount -o loop %s %s' % (virtio_floppy, virtio_mount)
            run(m_cmd, info='Could not mount virtio floppy driver')
            os.chdir(virtio_mount)
            path_list = glob.glob('*')
            for path in path_list:
                self.copy_to(path)
        finally:
            os.chdir(pwd)
            cleanup(virtio_mount)


    def setup_virtio_win2003(self, virtio_floppy, virtio_oemsetup_id):
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
        self._copy_virtio_drivers(virtio_floppy)
        txtsetup_oem = os.path.join(self.mount, 'txtsetup.oem')
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
        if default_driver != virtio_oemsetup_id:
            parser.set('Defaults', 'SCSI', virtio_oemsetup_id)
            fp = open(txtsetup_oem, 'w')
            parser.write(fp)
            fp.close()


    def setup_virtio_win2008(self, virtio_floppy):
        """
        Setup the install floppy with the virtio storage drivers, win2008 style.

        Win2008, Vista and 7 require people to point out the path to the drivers
        on the unattended file, so we just need to copy the drivers to the
        driver floppy disk.
        Process:

        1) Copy the virtio drivers on the virtio floppy to the install floppy
        """
        self._copy_virtio_drivers(virtio_floppy)


class CdromDisk(Disk):
    """
    Represents a CDROM disk that we can master according to our needs.
    """
    def __init__(self, path):
        print "Creating ISO unattended image %s" % path
        self.mount = tempfile.mkdtemp(prefix='cdrom_unattended_', dir='/tmp')
        self.path = path
        clean_old_image(path)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))


    def close(self):
        g_cmd = ('mkisofs -o %s -max-iso9660-filenames '
                 '-relaxed-filenames -D --input-charset iso8859-1 '
                 '%s' % (self.path, self.mount))
        run(g_cmd, info='Could not generate iso with answer file')

        os.chmod(self.path, 0755)
        cleanup(self.mount)
        print "Disk %s successfuly set" % self.path


class UnattendedInstall(object):
    """
    Creates a floppy disk image that will contain a config file for unattended
    OS install. The parameters to the script are retrieved from environment
    variables.
    """
    def __init__(self):
        """
        Gets params from environment variables and sets class attributes.
        """
        images_dir = os.path.join(KVM_TEST_DIR, 'images')
        self.deps_dir = os.path.join(KVM_TEST_DIR, 'deps')
        self.unattended_dir = os.path.join(KVM_TEST_DIR, 'unattended')

        attributes = ['kernel_args', 'finish_program', 'cdrom_cd1',
                      'unattended_file', 'medium', 'url', 'kernel', 'initrd',
                      'nfs_server', 'nfs_dir', 'install_virtio', 'floppy',
                      'cdrom_unattended', 'boot_path', 'extra_params']

        for a in attributes:
            self._setattr(a)

        if self.install_virtio == 'yes':
            v_attributes = ['virtio_floppy', 'virtio_storage_path',
                            'virtio_network_path', 'virtio_oemsetup_id',
                            'virtio_network_installer']
            for va in v_attributes:
                self._setattr(va)

        if self.cdrom_cd1:
            self.cdrom_cd1 = os.path.join(KVM_TEST_DIR, self.cdrom_cd1)
        self.cdrom_cd1_mount = tempfile.mkdtemp(prefix='cdrom_cd1_', dir='/tmp')
        if self.medium == 'nfs':
            self.nfs_mount = tempfile.mkdtemp(prefix='nfs_', dir='/tmp')

        if self.floppy:
            self.floppy = os.path.join(KVM_TEST_DIR, self.floppy)
            if not os.path.isdir(os.path.dirname(self.floppy)):
                os.makedirs(os.path.dirname(self.floppy))

        self.image_path = os.path.dirname(self.kernel)


    def _setattr(self, key):
        """
        Populate class attributes with contents of environment variables.

        Example: KVM_TEST_medium will populate self.medium.

        @param key: Name of the class attribute we desire to have.
        """
        env_name = 'KVM_TEST_%s' % key
        value = os.environ.get(env_name, '')
        setattr(self, key, value)


    def render_answer_file(self):
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

        print "Unattended install contents:"
        print unattended_contents
        return unattended_contents


    def setup_boot_disk(self):
        answer_contents = self.render_answer_file()

        if self.unattended_file.endswith('.sif'):
            dest_fname = 'winnt.sif'
            setup_file = 'winnt.bat'
            boot_disk = FloppyDisk(self.floppy)
            boot_disk.setup_answer_file(dest_fname, answer_contents)
            setup_file_path = os.path.join(self.unattended_dir, setup_file)
            boot_disk.copy_to(setup_file_path)
            if self.install_virtio == "yes":
                boot_disk.setup_virtio_win2003(self.virtio_floppy,
                                               self.virtio_oemsetup_id)
            boot_disk.copy_to(self.finish_program)

        elif self.unattended_file.endswith('.ks'):
            # Red Hat kickstart install
            dest_fname = 'ks.cfg'
            if self.cdrom_unattended:
                boot_disk = CdromDisk(self.cdrom_unattended)
            elif self.floppy:
                boot_disk = FloppyDisk(self.floppy)
            else:
                raise SetupError("Neither cdrom_unattended nor floppy set "
                                 "on the config file, please verify")
            boot_disk.setup_answer_file(dest_fname, answer_contents)

        elif self.unattended_file.endswith('.xml'):
            if "autoyast" in self.extra_params:
                # SUSE autoyast install
                dest_fname = "autoinst.xml"
                if self.cdrom_unattended:
                    boot_disk = CdromDisk(self.cdrom_unattended)
                elif self.floppy:
                    boot_disk = FloppyDisk(self.floppy)
                else:
                    raise SetupError("Neither cdrom_unattended nor floppy set "
                                     "on the config file, please verify")
                boot_disk.setup_answer_file(dest_fname, answer_contents)

            else:
                # Windows unattended install
                dest_fname = "autounattend.xml"
                boot_disk = FloppyDisk(self.floppy)
                boot_disk.setup_answer_file(dest_fname, answer_contents)
                if self.install_virtio == "yes":
                    boot_disk.setup_virtio_win2008(self.virtio_floppy)
                boot_disk.copy_to(self.finish_program)

        else:
            raise SetupError('Unknown answer file %s' %
                             self.unattended_file)

        boot_disk.close()


    def setup_cdrom(self):
        """
        Mount cdrom and copy vmlinuz and initrd.img.
        """
        print "Copying vmlinuz and initrd.img from cdrom"
        m_cmd = ('mount -t iso9660 -v -o loop,ro %s %s' %
                 (self.cdrom_cd1, self.cdrom_cd1_mount))
        run(m_cmd, info='Could not mount CD image %s.' % self.cdrom_cd1)

        try:
            img_path_cmd = ("mkdir -p %s" % self.image_path)
            run(img_path_cmd, info=("Could not create image path dir %s" %
                                    self.image_path))
            kernel_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.cdrom_cd1_mount, self.boot_path,
                                 os.path.basename(self.kernel), self.kernel))
            run(kernel_fetch_cmd, info=("Could not copy the vmlinuz from %s" %
                                        self.cdrom_cd1_mount))
            initrd_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.cdrom_cd1_mount, self.boot_path,
                                 os.path.basename(self.initrd), self.initrd))
            run(initrd_fetch_cmd, info=("Could not copy the initrd.img from "
                                        "%s" % self.cdrom_cd1_mount))
        finally:
            cleanup(self.cdrom_cd1_mount)


    def setup_url(self):
        """
        Download the vmlinuz and initrd.img from URL.
        """
        print "Downloading vmlinuz and initrd.img from URL"
        os.chdir(self.image_path)

        kernel_fetch_cmd = "wget -q %s/%s/%s" % (self.url, self.boot_path,
                                                 os.path.basename(self.kernel))
        initrd_fetch_cmd = "wget -q %s/%s/%s" % (self.url, self.boot_path,
                                                 os.path.basename(self.initrd))

        if os.path.exists(self.kernel):
            os.unlink(self.kernel)
        if os.path.exists(self.initrd):
            os.unlink(self.initrd)

        run(kernel_fetch_cmd, info="Could not fetch vmlinuz from %s" % self.url)
        run(initrd_fetch_cmd, info=("Could not fetch initrd.img from %s" %
                                    self.url))


    def setup_nfs(self):
        """
        Copy the vmlinuz and initrd.img from nfs.
        """
        print "Copying the vmlinuz and initrd.img from nfs"

        m_cmd = ("mount %s:%s %s -o ro" %
                 (self.nfs_server, self.nfs_dir, self.nfs_mount))
        run(m_cmd, info='Could not mount nfs server')

        try:
            kernel_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.nfs_mount, self.boot_path,
                                os.path.basename(self.kernel), self.image_path))
            run(kernel_fetch_cmd, info=("Could not copy the vmlinuz from %s" %
                                        self.nfs_mount))
            initrd_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.nfs_mount, self.boot_path,
                                os.path.basename(self.initrd), self.image_path))
            run(initrd_fetch_cmd, info=("Could not copy the initrd.img from "
                                        "%s" % self.nfs_mount))
        finally:
            cleanup(self.nfs_mount)


    def setup(self):
        """
        Configure the environment for unattended install.

        Uses an appropriate strategy according to each install model.
        """
        print "Starting unattended install setup"
        print

        print "Variables set:"
        for member in inspect.getmembers(self):
            name, value = member
            attribute = getattr(self, name)
            if not (name.startswith("__") or callable(attribute) or not value):
                print "    %s: %s" % (name, value)
        print

        if self.unattended_file and (self.floppy or self.cdrom_unattended):
            self.setup_boot_disk()
        if self.medium == "cdrom":
            if self.kernel and self.initrd:
                self.setup_cdrom()
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
