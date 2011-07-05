import logging, time, socket, re, os, shutil, tempfile, glob, ConfigParser
import xml.dom.minidom
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_vm, virt_utils


@error.context_aware
def cleanup(dir):
    """
    If dir is a mountpoint, do what is possible to unmount it. Afterwards,
    try to remove it.

    @param dir: Directory to be cleaned up.
    """
    error.context("cleaning up unattended install directory %s" % dir)
    if os.path.ismount(dir):
        utils.run('fuser -k %s' % dir, ignore_status=True)
        utils.run('umount %s' % dir)
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
            utils.run('fuser -k %s' % image, ignore_status=True)
            utils.run('umount %s' % image)
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
            utils.run(c_cmd)
            f_cmd = 'mkfs.msdos -s 1 %s' % path
            utils.run(f_cmd)
            m_cmd = 'mount -o loop,rw %s %s' % (path, self.mount)
            utils.run(m_cmd)
        except error.CmdError, e:
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
            utils.run(m_cmd)
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
        utils.run(g_cmd)

        os.chmod(self.path, 0755)
        cleanup(self.mount)
        logging.debug("unattended install CD image %s successfuly created",
                      self.path)


class UnattendedInstallConfig(object):
    """
    Creates a floppy disk image that will contain a config file for unattended
    OS install. The parameters to the script are retrieved from environment
    variables.
    """
    def __init__(self, test, params):
        """
        Sets class atributes from test parameters.

        @param test: KVM test object.
        @param params: Dictionary with test parameters.
        """
        root_dir = test.bindir
        images_dir = os.path.join(root_dir, 'images')
        self.deps_dir = os.path.join(root_dir, 'deps')
        self.unattended_dir = os.path.join(root_dir, 'unattended')

        attributes = ['kernel_args', 'finish_program', 'cdrom_cd1',
                      'unattended_file', 'medium', 'url', 'kernel', 'initrd',
                      'nfs_server', 'nfs_dir', 'install_virtio', 'floppy',
                      'cdrom_unattended', 'boot_path', 'extra_params',
                      'qemu_img_binary', 'cdkey', 'finish_program']

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
            self.unattended_file = os.path.join(root_dir, self.unattended_file)

        if getattr(self, 'finish_program'):
            self.finish_program = os.path.join(root_dir, self.finish_program)

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
        if self.medium == "cdrom":
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

        # Last, replace the virtio installer command
        if self.install_virtio == 'yes':
            driver = self.virtio_network_installer_path
        else:
            driver = 'dir'

        dummy_re = 'KVM_TEST_VIRTIO_NETWORK_INSTALLER'
        installer = parser.get('GuiRunOnce', 'Command0')
        if dummy_re in installer:
            installer = re.sub(dummy_re, driver, installer)
        parser.set('GuiRunOnce', 'Command0', installer)

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
        command_lines = doc.getElementsByTagName("CommandLine")
        for command_line in command_lines:
            command_line_text = command_line.childNodes[0]
            assert command_line_text.nodeType == doc.TEXT_NODE
            dummy_re = 'KVM_TEST_VIRTIO_NETWORK_INSTALLER'
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
            if self.cdrom_unattended:
                boot_disk = CdromDisk(self.cdrom_unattended, self.tmpdir)
            elif self.floppy:
                boot_disk = FloppyDisk(self.floppy, self.qemu_img_binary,
                                       self.tmpdir)
            else:
                raise ValueError("Neither cdrom_unattended nor floppy set "
                                 "on the config file, please verify")
            answer_path = boot_disk.get_answer_file_path(dest_fname)
            self.answer_kickstart(answer_path)

        elif self.unattended_file.endswith('.xml'):
            if "autoyast" in self.extra_params:
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
        m_cmd = ('mount -t iso9660 -v -o loop,ro %s %s' %
                 (self.cdrom_cd1, self.cdrom_cd1_mount))
        utils.run(m_cmd)

        try:
            if not os.path.isdir(self.image_path):
                os.makedirs(self.image_path)
            kernel_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.cdrom_cd1_mount, self.boot_path,
                                 os.path.basename(self.kernel), self.kernel))
            utils.run(kernel_fetch_cmd)
            initrd_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.cdrom_cd1_mount, self.boot_path,
                                 os.path.basename(self.initrd), self.initrd))
            utils.run(initrd_fetch_cmd)
        finally:
            cleanup(self.cdrom_cd1_mount)


    @error.context_aware
    def setup_url(self):
        """
        Download the vmlinuz and initrd.img from URL.
        """
        error.context("downloading vmlinuz and initrd.img from %s" % self.url)
        os.chdir(self.image_path)
        kernel_fetch_cmd = "wget -q %s/%s/%s" % (self.url, self.boot_path,
                                                 os.path.basename(self.kernel))
        initrd_fetch_cmd = "wget -q %s/%s/%s" % (self.url, self.boot_path,
                                                 os.path.basename(self.initrd))

        if os.path.exists(self.kernel):
            os.remove(self.kernel)
        if os.path.exists(self.initrd):
            os.remove(self.initrd)

        utils.run(kernel_fetch_cmd)
        utils.run(initrd_fetch_cmd)


    def setup_nfs(self):
        """
        Copy the vmlinuz and initrd.img from nfs.
        """
        error.context("copying the vmlinuz and initrd.img from NFS share")

        m_cmd = ("mount %s:%s %s -o ro" %
                 (self.nfs_server, self.nfs_dir, self.nfs_mount))
        utils.run(m_cmd)

        try:
            kernel_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.nfs_mount, self.boot_path,
                                os.path.basename(self.kernel), self.image_path))
            utils.run(kernel_fetch_cmd)
            initrd_fetch_cmd = ("cp %s/%s/%s %s" %
                                (self.nfs_mount, self.boot_path,
                                os.path.basename(self.initrd), self.image_path))
            utils.run(initrd_fetch_cmd)
        finally:
            cleanup(self.nfs_mount)


    def setup(self):
        """
        Configure the environment for unattended install.

        Uses an appropriate strategy according to each install model.
        """
        logging.info("Starting unattended install setup")
        virt_utils.display_attributes(self)

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
            raise ValueError("Unexpected installation method %s" %
                             self.medium)


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
    unattended_install_config = UnattendedInstallConfig(test, params)
    unattended_install_config.setup()
    vm = env.get_vm(params["main_vm"])
    vm.create()

    install_timeout = int(params.get("timeout", 3000))
    post_install_delay = int(params.get("post_install_delay", 0))
    port = vm.get_port(int(params.get("guest_port_unattended_install")))

    migrate_background = params.get("migrate_background") == "yes"
    if migrate_background:
        mig_timeout = float(params.get("mig_timeout", "3600"))
        mig_protocol = params.get("migration_protocol", "tcp")

    logging.info("Waiting for installation to finish. Timeout set to %d s "
                 "(%d min)", install_timeout, install_timeout/60)
    error.context("waiting for installation to finish")

    start_time = time.time()
    while (time.time() - start_time) < install_timeout:
        try:
            vm.verify_alive()
        except virt_vm.VMDeadError, e:
            if params.get("wait_no_ack", "no") == "yes":
                break
            else:
                raise e
        vm.verify_kernel_crash()
        if params.get("wait_no_ack", "no") == "no":
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                client.connect((vm.get_address(), port))
                if client.recv(1024) == "done":
                    break
            except (socket.error, virt_vm.VMAddressError):
                pass

        if migrate_background:
            # Drop the params which may break the migration
            # Better method is to use dnsmasq to do the
            # unattended installation
            if vm.params.get("initrd"):
                vm.params["initrd"] = None
            if vm.params.get("kernel"):
                vm.params["kernel"] = None
            if vm.params.get("extra_params"):
                vm.params["extra_params"] = re.sub("--append '.*'", "",
                                                   vm.params["extra_params"])
            vm.migrate(timeout=mig_timeout, protocol=mig_protocol)
        else:
            time.sleep(1)
        if params.get("wait_no_ack", "no") == "no":
            client.close()
    else:
        raise error.TestFail("Timeout elapsed while waiting for install to "
                             "finish")

    time_elapsed = time.time() - start_time
    logging.info("Guest reported successful installation after %d s (%d min)",
                 time_elapsed, time_elapsed/60)

    if params.get("shutdown_cleanly", "yes") == "yes":
        shutdown_cleanly_timeout = int(params.get("shutdown_cleanly_timeout",
                                                  120))
        logging.info("Wait for guest to shutdown cleanly")
        if virt_utils.wait_for(vm.is_dead, shutdown_cleanly_timeout, 1, 1):
            logging.info("Guest managed to shutdown cleanly")
