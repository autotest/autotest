import logging, time, re, os, shutil, tempfile, glob, ConfigParser
import threading
import xml.dom.minidom
from autotest.client.shared import error, iso9660
from autotest.client import utils
from autotest.client.virt import virt_vm, virt_utils, virt_http_server
from autotest.client.virt import kvm_monitor


# Whether to print all shell commands called
DEBUG = False

_url_auto_content_server_thread = None
_url_auto_content_server_thread_event = None

_unattended_server_thread = None
_unattended_server_thread_event = None


def start_auto_content_server_thread(port, path):
    global _url_auto_content_server_thread
    global _url_auto_content_server_thread_event

    if _url_auto_content_server_thread is None:
        _url_auto_content_server_thread_event = threading.Event()
        _url_auto_content_server_thread = threading.Thread(
            target=virt_http_server.http_server,
            args=(port, path, terminate_auto_content_server_thread))
        _url_auto_content_server_thread.start()


def start_unattended_server_thread(port, path):
    global _unattended_server_thread
    global _unattended_server_thread_event

    if _unattended_server_thread is None:
        _unattended_server_thread_event = threading.Event()
        _unattended_server_thread = threading.Thread(
            target=virt_http_server.http_server,
            args=(port, path, terminate_unattended_server_thread))
        _unattended_server_thread.start()


def terminate_auto_content_server_thread():
    global _url_auto_content_server_thread
    global _url_auto_content_server_thread_event

    if _url_auto_content_server_thread is None:
        return False
    if _url_auto_content_server_thread_event is None:
        return False

    if _url_auto_content_server_thread_event.isSet():
        return True

    return False


def terminate_unattended_server_thread():
    global _unattended_server_thread, _unattended_server_thread_event

    if _unattended_server_thread is None:
        return False
    if _unattended_server_thread_event is None:
        return False

    if  _unattended_server_thread_event.isSet():
        return True

    return False


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


class RemoteInstall(object):
    """
    Represents a install http server that we can master according to our needs.
    """
    def __init__(self, path, ip, port, filename):
        self.path = path
        cleanup(self.path)
        os.makedirs(self.path)
        self.ip = ip
        self.port = port
        self.filename = filename

        start_unattended_server_thread(self.port,self.path)


    def get_url(self):
        return 'http://%s:%s/%s' % (self.ip, self.port, self.filename)


    def get_answer_file_path(self, filename):
        return os.path.join(self.path, filename)


    def close(self):
        os.chmod(self.path, 0755)
        logging.debug("unattended http server %s successfully created",
                      self.get_url())


class UnattendedInstallConfig(object):
    """
    Creates a floppy disk image that will contain a config file for unattended
    OS install. The parameters to the script are retrieved from environment
    variables.
    """
    def __init__(self, test, params, vm):
        """
        Sets class atributes from test parameters.

        @param test: KVM test object.
        @param params: Dictionary with test parameters.
        """
        root_dir = test.bindir
        self.deps_dir = os.path.join(test.virtdir, 'deps')
        self.unattended_dir = os.path.join(test.virtdir, 'unattended')
        self.params = params

        attributes = ['kernel_args', 'finish_program', 'cdrom_cd1',
                      'unattended_file', 'medium', 'url', 'kernel', 'initrd',
                      'nfs_server', 'nfs_dir', 'install_virtio', 'floppy',
                      'cdrom_unattended', 'boot_path', 'kernel_params',
                      'extra_params', 'qemu_img_binary', 'cdkey',
                      'finish_program', 'vm_type', 'process_check']

        for a in attributes:
            setattr(self, a, params.get(a, ''))

        if self.install_virtio == 'yes':
            v_attributes = ['virtio_floppy', 'virtio_storage_path',
                            'virtio_network_path', 'virtio_oemsetup_id',
                            'virtio_network_installer']
            for va in v_attributes:
                setattr(self, va, params.get(va, ''))

        self.tmpdir = test.tmpdir

        if getattr(self, 'unattended_file'):
            self.unattended_file = os.path.join(test.virtdir, self.unattended_file)

        if getattr(self, 'finish_program'):
            self.finish_program = os.path.join(test.virtdir, self.finish_program)

        if getattr(self, 'qemu_img_binary'):
            if not os.path.isfile(getattr(self, 'qemu_img_binary')):
                self.qemu_img_binary = os.path.join(root_dir,
                                                    self.qemu_img_binary)

        if getattr(self, 'cdrom_cd1'):
            self.cdrom_cd1 = os.path.join(root_dir, self.cdrom_cd1)
        self.cdrom_cd1_mount = tempfile.mkdtemp(prefix='cdrom_cd1_',
                                                dir=self.tmpdir)
        if self.medium == 'nfs':
            self.nfs_mount = tempfile.mkdtemp(prefix='nfs_',
                                              dir=self.tmpdir)

        if getattr(self, 'floppy'):
            self.floppy = os.path.join(root_dir, self.floppy)
            if not os.path.isdir(os.path.dirname(self.floppy)):
                os.makedirs(os.path.dirname(self.floppy))

        self.image_path = os.path.dirname(self.kernel)

        # Content server params
        # lookup host ip address for first nic by interface name
        auto_ip = virt_utils.get_ip_address_by_interface(vm.virtnet[0].netdst)
        self.url_auto_content_ip = params.get('url_auto_ip', auto_ip)
        self.url_auto_content_port = None

        # Kickstart server params
        # use the same IP as url_auto_content_ip, but a different port
        self.unattended_server_port = None

        self.vm = vm


    def answer_kickstart(self, answer_path):
        """
        Replace KVM_TEST_CDKEY (in the unattended file) with the cdkey
        provided for this test and replace the KVM_TEST_MEDIUM with
        the tree url or nfs address provided for this test.

        @return: Answer file contents
        """
        contents = open(self.unattended_file).read()

        dummy_cdkey_re = r'\bKVM_TEST_CDKEY\b'
        if re.search(dummy_cdkey_re, contents):
            if self.cdkey:
                contents = re.sub(dummy_cdkey_re, self.cdkey, contents)

        dummy_medium_re = r'\bKVM_TEST_MEDIUM\b'
        if self.medium in ["cdrom", "kernel_initrd"]:
            content = "cdrom"

        elif self.medium == "url":
            content = "url --url %s" % self.url

        elif self.medium == "nfs":
            content = "nfs --server=%s --dir=%s" % (self.nfs_server,
                                                    self.nfs_dir)
        else:
            raise ValueError("Unexpected installation medium %s" % self.url)

        contents = re.sub(dummy_medium_re, content, contents)

        logging.debug("Unattended install contents:")
        for line in contents.splitlines():
            logging.debug(line)

        utils.open_write_close(answer_path, contents)


    def answer_windows_ini(self, answer_path):
        parser = ConfigParser.ConfigParser()
        parser.read(self.unattended_file)
        # First, replacing the CDKEY
        if self.cdkey:
            parser.set('UserData', 'ProductKey', self.cdkey)
        else:
            logging.error("Param 'cdkey' required but not specified for "
                          "this unattended installation")

        # Now, replacing the virtio network driver path, under double quotes
        if self.install_virtio == 'yes':
            parser.set('Unattended', 'OemPnPDriversPath',
                       '"%s"' % self.virtio_nework_path)
        else:
            parser.remove_option('Unattended', 'OemPnPDriversPath')

        # Replace the virtio installer command
        if self.install_virtio == 'yes':
            driver = self.virtio_network_installer_path
        else:
            driver = 'dir'

        dummy_re = 'KVM_TEST_VIRTIO_NETWORK_INSTALLER'
        installer = parser.get('GuiRunOnce', 'Command0')
        if dummy_re in installer:
            installer = re.sub(dummy_re, driver, installer)
        parser.set('GuiRunOnce', 'Command0', installer)

        # Replace the process check in finish command
        dummy_process_re = r'\bPROCESS_CHECK\b'
        for opt in parser.options('GuiRunOnce'):
            process_check = parser.get('GuiRunOnce', opt)
            if re.search(dummy_process_re, process_check):
                process_check = re.sub(dummy_process_re,
                              "%s" % self.process_check,
                              process_check)
                parser.set('GuiRunOnce', opt, process_check)

        # Now, writing the in memory config state to the unattended file
        fp = open(answer_path, 'w')
        parser.write(fp)

        # Let's read it so we can debug print the contents
        fp = open(answer_path, 'r')
        contents = fp.read()
        logging.debug("Unattended install contents:")
        for line in contents.splitlines():
            logging.debug(line)
        fp.close()


    def answer_windows_xml(self, answer_path):
        doc = xml.dom.minidom.parse(self.unattended_file)

        if self.cdkey:
            # First, replacing the CDKEY
            product_key = doc.getElementsByTagName('ProductKey')[0]
            key = product_key.getElementsByTagName('Key')[0]
            key_text = key.childNodes[0]
            assert key_text.nodeType == doc.TEXT_NODE
            key_text.data = self.cdkey
        else:
            logging.error("Param 'cdkey' required but not specified for "
                          "this unattended installation")

        # Now, replacing the virtio driver paths or removing the entire
        # component PnpCustomizationsWinPE Element Node
        if self.install_virtio == 'yes':
            paths = doc.getElementsByTagName("Path")
            values = [self.virtio_storage_path, self.virtio_network_path]
            for path, value in zip(paths, values):
                path_text = path.childNodes[0]
                assert key_text.nodeType == doc.TEXT_NODE
                path_text.data = value
        else:
            settings = doc.getElementsByTagName("settings")
            for s in settings:
                for c in s.getElementsByTagName("component"):
                    if (c.getAttribute('name') ==
                        "Microsoft-Windows-PnpCustomizationsWinPE"):
                        s.removeChild(c)

        # Last but not least important, replacing the virtio installer command
        # And process check in finish command
        command_lines = doc.getElementsByTagName("CommandLine")
        for command_line in command_lines:
            command_line_text = command_line.childNodes[0]
            assert command_line_text.nodeType == doc.TEXT_NODE
            dummy_re = 'KVM_TEST_VIRTIO_NETWORK_INSTALLER'
            process_check_re = 'PROCESS_CHECK'
            if (self.install_virtio == 'yes' and
                hasattr(self, 'virtio_network_installer_path')):
                driver = self.virtio_network_installer_path
            else:
                driver = 'dir'
            if driver.endswith("msi"):
                driver = 'msiexec /passive /package ' + driver
            if dummy_re in command_line_text.data:
                t = command_line_text.data
                t = re.sub(dummy_re, driver, t)
                command_line_text.data = t
            if process_check_re in command_line_text.data:
                t = command_line_text.data
                t = re.sub(process_check_re, self.process_check, t)
                command_line_text.data = t

        contents = doc.toxml()
        logging.debug("Unattended install contents:")
        for line in contents.splitlines():
            logging.debug(line)

        fp = open(answer_path, 'w')
        doc.writexml(fp)


    def answer_suse_xml(self, answer_path):
        # There's nothing to replace on SUSE files to date. Yay!
        doc = xml.dom.minidom.parse(self.unattended_file)

        contents = doc.toxml()
        logging.debug("Unattended install contents:")
        for line in contents.splitlines():
            logging.debug(line)

        fp = open(answer_path, 'w')
        doc.writexml(fp)


    def preseed_initrd(self):
        """
        Puts a preseed file inside a gz compressed initrd file.

        Debian and Ubuntu use preseed as the OEM install mechanism. The only
        way to get fully automated setup without resorting to kernel params
        is to add a preseed.cfg file at the root of the initrd image.
        """
        logging.debug("Remastering initrd.gz file with preseed file")
        dest_fname = 'preseed.cfg'
        remaster_path = os.path.join(self.image_path, "initrd_remaster")
        if not os.path.isdir(remaster_path):
            os.makedirs(remaster_path)

        base_initrd = os.path.basename(self.initrd)
        os.chdir(remaster_path)
        utils.run("gzip -d < ../%s | cpio --extract --make-directories "
                  "--no-absolute-filenames" % base_initrd, verbose=DEBUG)
        utils.run("cp %s %s" % (self.unattended_file, dest_fname),
                  verbose=DEBUG)

        if self.params.get("vm_type") == "libvirt":
            utils.run("find . | cpio -H newc --create > ../%s.img" %
                      base_initrd.rstrip(".gz"), verbose=DEBUG)
        else:
            utils.run("find . | cpio -H newc --create | gzip -9 > ../%s" %
                      base_initrd, verbose=DEBUG)

        os.chdir(self.image_path)
        utils.run("rm -rf initrd_remaster", verbose=DEBUG)
        contents = open(self.unattended_file).read()

        logging.debug("Unattended install contents:")
        for line in contents.splitlines():
            logging.debug(line)


    def setup_unattended_http_server(self):
        '''
        Setup a builtin http server for serving the kickstart file

        Does nothing if unattended file is not a kickstart file
        '''
        if self.unattended_file.endswith('.ks'):
            # Red Hat kickstart install
            dest_fname = 'ks.cfg'

            answer_path = os.path.join(self.tmpdir, dest_fname)
            self.answer_kickstart(answer_path)

            if self.unattended_server_port is None:
                self.unattended_server_port = virt_utils.find_free_port(
                    8000,
                    8099,
                    self.url_auto_content_ip)

            start_unattended_server_thread(self.unattended_server_port,
                                           self.tmpdir)

        # Point installation to this kickstart url
        ks_param = 'ks=http://%s:%s/%s' % (self.url_auto_content_ip,
                                           self.unattended_server_port,
                                           dest_fname)
        self.kernel_params = getattr(self, 'kernel_params')
        if 'ks=' in self.kernel_params:
            kernel_params = re.sub('ks\=[\w\d\:\.\/]+',
                                  ks_param,
                                  self.kernel_params)
        else:
            kernel_params = '%s %s' % (self.kernel_params, ks_param)

        # reflect change on params
        self.kernel_params = kernel_params
        self.params['kernel_params'] = self.kernel_params


    def setup_boot_disk(self):
        if self.unattended_file.endswith('.sif'):
            dest_fname = 'winnt.sif'
            setup_file = 'winnt.bat'
            boot_disk = FloppyDisk(self.floppy, self.qemu_img_binary,
                                   self.tmpdir)
            answer_path = boot_disk.get_answer_file_path(dest_fname)
            self.answer_windows_ini(answer_path)
            setup_file_path = os.path.join(self.unattended_dir, setup_file)
            boot_disk.copy_to(setup_file_path)
            if self.install_virtio == "yes":
                boot_disk.setup_virtio_win2003(self.virtio_floppy,
                                               self.virtio_oemsetup_id)
            boot_disk.copy_to(self.finish_program)

        elif self.unattended_file.endswith('.ks'):
            # Red Hat kickstart install
            dest_fname = 'ks.cfg'
            if self.params.get('unattended_delivery_method') == 'integrated':
                ks_param = 'ks=cdrom:/dev/sr0:/isolinux/%s' % dest_fname
                kernel_params = getattr(self, 'kernel_params')
                if 'ks=' in kernel_params:
                    kernel_params = re.sub('ks\=[\w\d\:\.\/]+',
                                           ks_param,
                                           kernel_params)
                else:
                    kernel_params = '%s %s' % (kernel_params, ks_param)

                # Standard setting is kickstart disk in /dev/sr0 and
                # install cdrom in /dev/sr1. As we merge them together,
                # we need to change repo configuration to /dev/sr0
                if 'repo=cdrom' in kernel_params:
                    kernel_params = re.sub('repo\=cdrom[\:\w\d\/]*',
                                           'repo=cdrom:/dev/sr0',
                                           kernel_params)

                self.params['kernel_params'] = ''
                boot_disk = CdromInstallDisk(self.cdrom_unattended,
                                             self.tmpdir,
                                             self.cdrom_cd1_mount,
                                             kernel_params)
            elif self.params.get('unattended_delivery_method') == 'url':
                if self.unattended_server_port is None:
                    self.unattended_server_port = virt_utils.find_free_port(
                        8000,
                        8099,
                        self.url_auto_content_ip)
                path = os.path.join(os.path.dirname(self.cdrom_unattended),
                                    'ks')
                boot_disk = RemoteInstall(path, self.url_auto_content_ip,
                                          self.unattended_server_port,
                                          dest_fname)
                ks_param = 'ks=%s' % boot_disk.get_url()
                kernel_params = getattr(self, 'kernel_params')
                if 'ks=' in kernel_params:
                    kernel_params = re.sub('ks\=[\w\d\:\.\/]+',
                                          ks_param,
                                          kernel_params)
                else:
                    kernel_params = '%s %s' % (kernel_params, ks_param)

                # Standard setting is kickstart disk in /dev/sr0 and
                # install cdrom in /dev/sr1. When we get ks via http,
                # we need to change repo configuration to /dev/sr0
                if 'repo=cdrom' in kernel_params:
                    kernel_params = re.sub('repo\=cdrom[\:\w\d\/]*',
                                           'repo=cdrom:/dev/sr0',
                                           kernel_params)

                self.params['kernel_params'] = kernel_params
            elif self.params.get('unattended_delivery_method') == 'cdrom':
                boot_disk = CdromDisk(self.cdrom_unattended, self.tmpdir)
            elif self.params.get('unattended_delivery_method') == 'floppy':
                boot_disk = FloppyDisk(self.floppy, self.qemu_img_binary,
                                       self.tmpdir)
            else:
                raise ValueError("Neither cdrom_unattended nor floppy set "
                                 "on the config file, please verify")
            answer_path = boot_disk.get_answer_file_path(dest_fname)
            self.answer_kickstart(answer_path)

        elif self.unattended_file.endswith('.xml'):
            if "autoyast" in self.kernel_params:
                # SUSE autoyast install
                dest_fname = "autoinst.xml"
                if self.cdrom_unattended:
                    boot_disk = CdromDisk(self.cdrom_unattended, self.tmpdir)
                elif self.floppy:
                    boot_disk = FloppyDisk(self.floppy, self.qemu_img_binary,
                                           self.tmpdir)
                else:
                    raise ValueError("Neither cdrom_unattended nor floppy set "
                                     "on the config file, please verify")
                answer_path = boot_disk.get_answer_file_path(dest_fname)
                self.answer_suse_xml(answer_path)

            else:
                # Windows unattended install
                dest_fname = "autounattend.xml"
                boot_disk = FloppyDisk(self.floppy, self.qemu_img_binary,
                                       self.tmpdir)
                answer_path = boot_disk.get_answer_file_path(dest_fname)
                self.answer_windows_xml(answer_path)

                if self.install_virtio == "yes":
                    boot_disk.setup_virtio_win2008(self.virtio_floppy)
                boot_disk.copy_to(self.finish_program)

        else:
            raise ValueError('Unknown answer file type: %s' %
                             self.unattended_file)

        boot_disk.close()


    @error.context_aware
    def setup_cdrom(self):
        """
        Mount cdrom and copy vmlinuz and initrd.img.
        """
        error.context("Copying vmlinuz and initrd.img from install cdrom %s" %
                      self.cdrom_cd1)
        if not os.path.isdir(self.image_path):
            os.makedirs(self.image_path)

        if (self.params.get('unattended_delivery_method') in
            ['integrated', 'url']):
            i = iso9660.Iso9660Mount(self.cdrom_cd1)
            self.cdrom_cd1_mount = i.mnt_dir
        else:
            i = iso9660.iso9660(self.cdrom_cd1)

        if i is None:
            raise error.TestFail("Could not instantiate an iso9660 class")

        i.copy(os.path.join(self.boot_path, os.path.basename(self.kernel)),
               self.kernel)
        assert(os.path.getsize(self.kernel) > 0)
        i.copy(os.path.join(self.boot_path, os.path.basename(self.initrd)),
               self.initrd)
        assert(os.path.getsize(self.initrd) > 0)

        if self.unattended_file.endswith('.preseed'):
            self.preseed_initrd()

        if self.params.get("vm_type") == "libvirt":
            if self.vm.driver_type == 'qemu':
                # Virtinstall command needs files "vmlinuz" and "initrd.img"
                os.chdir(self.image_path)
                base_kernel = os.path.basename(self.kernel)
                base_initrd = os.path.basename(self.initrd)
                if base_kernel != 'vmlinuz':
                    utils.run("mv %s vmlinuz" % base_kernel, verbose=DEBUG)
                if base_initrd != 'initrd.img':
                    utils.run("mv %s initrd.img" % base_initrd, verbose=DEBUG)
                if (self.params.get('unattended_delivery_method') !=
                    'integrated'):
                    i.close()
                    cleanup(self.cdrom_cd1_mount)
            elif ((self.vm.driver_type == 'xen') and
                  (self.params.get('hvm_or_pv') == 'pv')):
                logging.debug("starting unattended content web server")

                self.url_auto_content_port = virt_utils.find_free_port(8100,
                                                                       8199,
                                                       self.url_auto_content_ip)

                start_auto_content_server_thread(self.url_auto_content_port,
                                                 self.cdrom_cd1_mount)

                self.medium = 'url'
                self.url = ('http://%s:%s' % (self.url_auto_content_ip,
                                              self.url_auto_content_port))

                pxe_path = os.path.join(os.path.dirname(self.image_path), 'xen')
                if not os.path.isdir(pxe_path):
                    os.makedirs(pxe_path)

                pxe_kernel = os.path.join(pxe_path,
                                          os.path.basename(self.kernel))
                pxe_initrd = os.path.join(pxe_path,
                                          os.path.basename(self.initrd))
                utils.run("cp %s %s" % (self.kernel, pxe_kernel))
                utils.run("cp %s %s" % (self.initrd, pxe_initrd))


    @error.context_aware
    def setup_url_auto(self):
        """
        Configures the builtin web server for serving content
        """
        auto_content_url = 'http://%s:%s' % (self.url_auto_content_ip,
                                             self.url_auto_content_port)
        self.params['auto_content_url'] = auto_content_url


    @error.context_aware
    def setup_url(self):
        """
        Download the vmlinuz and initrd.img from URL.
        """
        # it's only necessary to download kernel/initrd if running bare qemu
        if self.vm_type == 'kvm':
            error.context("downloading vmlinuz/initrd.img from %s" % self.url)
            os.chdir(self.image_path)
            kernel_cmd = "wget -q %s/%s/%s" % (self.url,
                                               self.boot_path,
                                               os.path.basename(self.kernel))
            initrd_cmd = "wget -q %s/%s/%s" % (self.url,
                                               self.boot_path,
                                               os.path.basename(self.initrd))

            if os.path.exists(self.kernel):
                os.remove(self.kernel)
            if os.path.exists(self.initrd):
                os.remove(self.initrd)

            utils.run(kernel_cmd, verbose=DEBUG)
            utils.run(initrd_cmd, verbose=DEBUG)

        elif self.vm_type == 'libvirt':
            logging.info("Not downloading vmlinuz/initrd.img from %s, "
                         "letting virt-install do it instead")

        else:
            logging.info("No action defined/needed for the current virt "
                         "type: '%s'" % self.vm_type)


    def setup_nfs(self):
        """
        Copy the vmlinuz and initrd.img from nfs.
        """
        error.context("copying the vmlinuz and initrd.img from NFS share")

        m_cmd = ("mount %s:%s %s -o ro" %
                 (self.nfs_server, self.nfs_dir, self.nfs_mount))
        utils.run(m_cmd, verbose=DEBUG)

        try:
            kernel_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.nfs_mount, self.boot_path,
                                os.path.basename(self.kernel), self.image_path))
            utils.run(kernel_fetch_cmd, verbose=DEBUG)
            initrd_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.nfs_mount, self.boot_path,
                                os.path.basename(self.initrd), self.image_path))
            utils.run(initrd_fetch_cmd, verbose=DEBUG)
        finally:
            cleanup(self.nfs_mount)


    def setup_import(self):
        self.unattended_file = None
        self.params['kernel_params'] = None


    def setup(self):
        """
        Configure the environment for unattended install.

        Uses an appropriate strategy according to each install model.
        """
        logging.info("Starting unattended install setup")
        if DEBUG:
            virt_utils.display_attributes(self)

        if self.medium in ["cdrom", "kernel_initrd"]:
            if self.kernel and self.initrd:
                self.setup_cdrom()
        elif self.medium == "url":
            self.setup_url()
        elif self.medium == "nfs":
            self.setup_nfs()
        elif self.medium == "import":
            self.setup_import()
        else:
            raise ValueError("Unexpected installation method %s" %
                             self.medium)
        if self.unattended_file and (self.floppy or self.cdrom_unattended):
            self.setup_boot_disk()


@error.context_aware
def run_unattended_install(test, params, env):
    """
    Unattended install test:
    1) Starts a VM with an appropriated setup to start an unattended OS install.
    2) Wait until the install reports to the install watcher its end.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    unattended_install_config = UnattendedInstallConfig(test, params, vm)
    unattended_install_config.setup()

    # params passed explicitly, because they may have been updated by
    # unattended install config code, such as when params['url'] == auto
    vm.create(params=params)

    post_finish_str = params.get("post_finish_str",
                                 "Post set up finished")
    install_timeout = int(params.get("timeout", 3000))
    port = vm.get_port(int(params.get("guest_port_unattended_install")))

    migrate_background = params.get("migrate_background") == "yes"
    if migrate_background:
        mig_timeout = float(params.get("mig_timeout", "3600"))
        mig_protocol = params.get("migration_protocol", "tcp")

    logging.info("Waiting for installation to finish. Timeout set to %d s "
                 "(%d min)", install_timeout, install_timeout / 60)
    error.context("waiting for installation to finish")

    start_time = time.time()
    while (time.time() - start_time) < install_timeout:
        try:
            vm.verify_alive()
        # Due to a race condition, sometimes we might get a MonitorError
        # before the VM gracefully shuts down, so let's capture MonitorErrors.
        except (virt_vm.VMDeadError, kvm_monitor.MonitorError), e:
            if params.get("wait_no_ack", "no") == "yes":
                break
            else:
                raise e
        vm.verify_kernel_crash()
        finish_signal = vm.serial_console.get_output()
        if (params.get("wait_no_ack", "no") == "no" and
            (post_finish_str in finish_signal)):
            break

        # Due to libvirt automatically start guest after import
        # we only need to wait for successful login.
        if params.get("medium") == "import":
            try:
                vm.login()
                break
            except (virt_utils.LoginError, Exception), e:
                pass

        if migrate_background:
            vm.migrate(timeout=mig_timeout, protocol=mig_protocol)
        else:
            time.sleep(1)
    else:
        raise error.TestFail("Timeout elapsed while waiting for install to "
                             "finish")

    logging.debug('cleaning up threads and mounts that may be active')
    global _url_auto_content_server_thread
    global _url_auto_content_server_thread_event
    if _url_auto_content_server_thread is not None:
        _url_auto_content_server_thread_event.set()
        _url_auto_content_server_thread.join(3)
        _url_auto_content_server_thread = None
        cleanup(unattended_install_config.cdrom_cd1_mount)

    global _unattended_server_thread
    global _unattended_server_thread_event
    if _unattended_server_thread is not None:
        _unattended_server_thread_event.set()
        _unattended_server_thread.join(3)
        _unattended_server_thread = None

    time_elapsed = time.time() - start_time
    logging.info("Guest reported successful installation after %d s (%d min)",
                 time_elapsed, time_elapsed / 60)

    if params.get("shutdown_cleanly", "yes") == "yes":
        shutdown_cleanly_timeout = int(params.get("shutdown_cleanly_timeout",
                                                  120))
        logging.info("Wait for guest to shutdown cleanly")
        try:
            if virt_utils.wait_for(vm.is_dead, shutdown_cleanly_timeout, 1, 1):
                logging.info("Guest managed to shutdown cleanly")
        except kvm_monitor.MonitorError, e:
            logging.warning("Guest apparently shut down, but got a "
                            "monitor error: %s", e)
