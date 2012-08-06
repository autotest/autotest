"""
Virtualization test - Virtual disk related utility functions

@copyright: Red Hat Inc.
"""

import os, glob, shutil, tempfile, logging, ConfigParser
from autotest.client import utils
from autotest.client.shared import error


# Whether to print all shell commands called
DEBUG = False


@error.context_aware
def cleanup(dir):
    """
    If dir is a mountpoint, do what is possible to unmount it. Afterwards,
    try to remove it.

    @param dir: Directory to be cleaned up.
    """
    error.context("cleaning up unattended install directory %s" % dir)
    if os.path.ismount(dir):
        utils.run('fuser -k %s' % dir, ignore_status=True, verbose=DEBUG)
        utils.run('umount %s' % dir, verbose=DEBUG)
    if os.path.isdir(dir):
        shutil.rmtree(dir)


@error.context_aware
def clean_old_image(image):
    """
    Clean a leftover image file from previous processes. If it contains a
    mounted file system, do the proper cleanup procedures.

    @param image: Path to image to be cleaned up.
    """
    error.context("cleaning up old leftover image %s" % image)
    if os.path.exists(image):
        mtab = open('/etc/mtab', 'r')
        mtab_contents = mtab.read()
        mtab.close()
        if image in mtab_contents:
            utils.run('fuser -k %s' % image, ignore_status=True, verbose=DEBUG)
            utils.run('umount %s' % image, verbose=DEBUG)
        os.remove(image)


class Disk(object):
    """
    Abstract class for Disk objects, with the common methods implemented.
    """
    def __init__(self):
        self.path = None


    def get_answer_file_path(self, filename):
        return os.path.join(self.mount, filename)


    def copy_to(self, src):
        logging.debug("Copying %s to disk image mount", src)
        dst = os.path.join(self.mount, os.path.basename(src))
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.isfile(src):
            shutil.copyfile(src, dst)


    def close(self):
        os.chmod(self.path, 0755)
        cleanup(self.mount)
        logging.debug("Disk %s successfuly set", self.path)


class FloppyDisk(Disk):
    """
    Represents a 1.44 MB floppy disk. We can copy files to it, and setup it in
    convenient ways.
    """
    @error.context_aware
    def __init__(self, path, qemu_img_binary, tmpdir):
        error.context("Creating unattended install floppy image %s" % path)
        self.tmpdir = tmpdir
        self.mount = tempfile.mkdtemp(prefix='floppy_', dir=self.tmpdir)
        self.virtio_mount = None
        self.path = path
        clean_old_image(path)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        try:
            c_cmd = '%s create -f raw %s 1440k' % (qemu_img_binary, path)
            utils.run(c_cmd, verbose=DEBUG)
            f_cmd = 'mkfs.msdos -s 1 %s' % path
            utils.run(f_cmd, verbose=DEBUG)
            m_cmd = 'mount -o loop,rw %s %s' % (path, self.mount)
            utils.run(m_cmd, verbose=DEBUG)
        except error.CmdError, e:
            logging.error("Error during floppy initialization: %s" % e)
            cleanup(self.mount)
            raise


    def _copy_virtio_drivers(self, virtio_floppy):
        """
        Copy the virtio drivers on the virtio floppy to the install floppy.

        1) Mount the floppy containing the viostor drivers
        2) Copy its contents to the root of the install floppy
        """
        virtio_mount = tempfile.mkdtemp(prefix='virtio_floppy_',
                                        dir=self.tmpdir)

        pwd = os.getcwd()
        try:
            m_cmd = 'mount -o loop,ro %s %s' % (virtio_floppy, virtio_mount)
            utils.run(m_cmd, verbose=DEBUG)
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
            raise IOError('File txtsetup.oem not found on the install '
                          'floppy. Please verify if your floppy virtio '
                          'driver image has this file')
        parser = ConfigParser.ConfigParser()
        parser.read(txtsetup_oem)
        if not parser.has_section('Defaults'):
            raise ValueError('File txtsetup.oem does not have the session '
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
        driver floppy disk. Important to note that it's possible to specify
        drivers from a CDROM, so the floppy driver copy is optional.
        Process:

        1) Copy the virtio drivers on the virtio floppy to the install floppy,
           if there is one available
        """
        if os.path.isfile(virtio_floppy):
            self._copy_virtio_drivers(virtio_floppy)
        else:
            logging.debug("No virtio floppy present, not needed for this OS anyway")


class CdromDisk(Disk):
    """
    Represents a CDROM disk that we can master according to our needs.
    """
    def __init__(self, path, tmpdir):
        self.mount = tempfile.mkdtemp(prefix='cdrom_unattended_', dir=tmpdir)
        self.path = path
        clean_old_image(path)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))


    @error.context_aware
    def close(self):
        error.context("Creating unattended install CD image %s" % self.path)
        g_cmd = ('mkisofs -o %s -max-iso9660-filenames '
                 '-relaxed-filenames -D --input-charset iso8859-1 '
                 '%s' % (self.path, self.mount))
        utils.run(g_cmd, verbose=DEBUG)

        os.chmod(self.path, 0755)
        cleanup(self.mount)
        logging.debug("unattended install CD image %s successfuly created",
                      self.path)


class CdromInstallDisk(Disk):
    """
    Represents a install CDROM disk that we can master according to our needs.
    """
    def __init__(self, path, tmpdir, source_cdrom, extra_params):
        self.mount = tempfile.mkdtemp(prefix='cdrom_unattended_', dir=tmpdir)
        self.path = path
        self.extra_params = extra_params
        self.source_cdrom = source_cdrom
        cleanup(path)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        cp_cmd = ('cp -r %s/isolinux/ %s/' % (source_cdrom, self.mount))
        listdir = os.listdir(self.source_cdrom)
        for i in listdir:
            if i == 'isolinux':
                continue
            os.symlink(os.path.join(self.source_cdrom, i),
                       os.path.join(self.mount, i))
        utils.run(cp_cmd)


    def get_answer_file_path(self, filename):
        return os.path.join(self.mount, 'isolinux', filename)


    @error.context_aware
    def close(self):
        error.context("Creating unattended install CD image %s" % self.path)
        f = open(os.path.join(self.mount, 'isolinux', 'isolinux.cfg'), 'w')
        f.write('default /isolinux/vmlinuz append initrd=/isolinux/initrd.img '
                '%s\n' % self.extra_params)
        f.close()
        m_cmd = ('mkisofs -o %s -b isolinux/isolinux.bin -c isolinux/boot.cat '
                 '-no-emul-boot -boot-load-size 4 -boot-info-table -f -R -J '
                 '-V -T %s' % (self.path, self.mount))
        utils.run(m_cmd)
        os.chmod(self.path, 0755)
        cleanup(self.mount)
        cleanup(self.source_cdrom)
        logging.debug("unattended install CD image %s successfully created",
                      self.path)


