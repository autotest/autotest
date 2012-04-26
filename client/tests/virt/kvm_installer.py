"""
Installer code that implement KVM specific bits.

See BaseInstaller class in base_installer.py for interface details.
"""

import os, logging
from autotest.client import utils
from autotest.client.shared import error
from autotest.client.tests.virt import base_installer


__all__ = ['GitRepoInstaller', 'LocalSourceDirInstaller',
           'LocalSourceTarInstaller', 'RemoteSourceTarInstaller']


class KVMBaseInstaller(base_installer.BaseInstaller):
    '''
    Base class for KVM installations
    '''

    #
    # Name of acceptable QEMU binaries that may be built or installed.
    # We'll look for one of these binaries when linking the QEMU binary
    # to the test directory
    #
    ACCEPTABLE_QEMU_BIN_NAMES = ['qemu-kvm',
                                 'qemu-system-x86_64']

    #
    # The default names for the binaries
    #
    QEMU_BIN = 'qemu'
    QEMU_IMG_BIN = 'qemu-img'
    QEMU_IO_BIN = 'qemu-io'
    QEMU_FS_PROXY_BIN = 'virtfs-proxy-helper'


    def _kill_qemu_processes(self):
        """
        Kills all qemu processes and all processes holding /dev/kvm down

        @return: None
        """
        logging.debug("Killing any qemu processes that might be left behind")
        utils.system("pkill qemu", ignore_status=True)
        # Let's double check to see if some other process is holding /dev/kvm
        if os.path.isfile("/dev/kvm"):
            utils.system("fuser -k /dev/kvm", ignore_status=True)


    def _cleanup_links_qemu(self):
        '''
        Removes previously created links, if they exist

        @return: None
        '''
        qemu_path = os.path.join(self.test_bindir, self.QEMU_BIN)
        qemu_img_path = os.path.join(self.test_bindir, self.QEMU_IMG_BIN)
        qemu_io_path = os.path.join(self.test_bindir, self.QEMU_IO_BIN)
        qemu_fs_proxy_path = os.path.join(self.test_bindir,
                                          self.QEMU_FS_PROXY_BIN)

        # clean up previous links, if they exist
        for path in (qemu_path, qemu_img_path, qemu_io_path,
                     qemu_fs_proxy_path):
            if os.path.lexists(path):
                os.unlink(path)


    def _cleanup_link_unittest(self):
        '''
        Removes previously created links, if they exist

        @return: None
        '''
        qemu_unittest_path = os.path.join(self.test_bindir, "unittests")

        if os.path.lexists(qemu_unittest_path):
            os.unlink(qemu_unittest_path)


    def _create_symlink_unittest(self):
        '''
        Create symbolic links for qemu and qemu-img commands on test bindir

        @return: None
        '''
        unittest_src = os.path.join(self.install_prefix,
                                    'share', 'qemu', 'tests')
        unittest_dst = os.path.join(self.test_bindir, "unittests")

        if os.path.lexists(unittest_dst):
            logging.debug("Unlinking unittest dir")
            os.unlink(unittest_dst)

        logging.debug("Linking unittest dir")
        os.symlink(unittest_src, unittest_dst)


    def _qemu_bin_exists_at_prefix(self):
        '''
        Attempts to find the QEMU binary at the installation prefix

        @return: full path of QEMU binary or None if not found
        '''
        result = None

        for name in self.ACCEPTABLE_QEMU_BIN_NAMES:
            qemu_bin_name = os.path.join(self.install_prefix, 'bin', name)
            if os.path.isfile(qemu_bin_name):
                result = qemu_bin_name
                break

        if result is not None:
            logging.debug('Found QEMU binary at %s', result)
        else:
            logging.debug('Could not find QEMU binary at prefix %s',
                          self.install_prefix)

        return result


    def _qemu_img_bin_exists_at_prefix(self):
        '''
        Attempts to find the qemu-img binary at the installation prefix

        @return: full path of qemu-img binary or None if not found
        '''
        qemu_img_bin_name = os.path.join(self.install_prefix,
                                         'bin', self.QEMU_IMG_BIN)
        if os.path.isfile(qemu_img_bin_name):
            logging.debug('Found qemu-img binary at %s', qemu_img_bin_name)
            return qemu_img_bin_name
        else:
            logging.debug('Could not find qemu-img binary at prefix %s',
                          self.install_prefix)
            return None


    def _qemu_io_bin_exists_at_prefix(self):
        '''
        Attempts to find the qemu-io binary at the installation prefix

        @return: full path of qemu-io binary or None if not found
        '''
        qemu_io_bin_name = os.path.join(self.install_prefix,
                                         'bin', self.QEMU_IO_BIN)
        if os.path.isfile(qemu_io_bin_name):
            logging.debug('Found qemu-io binary at %s', qemu_io_bin_name)
            return qemu_io_bin_name
        else:
            logging.debug('Could not find qemu-io binary at prefix %s',
                          self.install_prefix)
            return None


    def _qemu_fs_proxy_bin_exists_at_prefix(self):
        '''
        Attempts to find the qemu fs proxy binary at the installation prefix

        @return: full path of qemu fs proxy binary or None if not found
        '''
        qemu_fs_proxy_bin_name = os.path.join(self.install_prefix,
                                              'bin', self.QEMU_FS_PROXY_BIN)
        if os.path.isfile(qemu_fs_proxy_bin_name):
            logging.debug('Found qemu fs proxy binary at %s',
                          qemu_fs_proxy_bin_name)
            return qemu_fs_proxy_bin_name
        else:
            logging.debug('Could not find qemu fs proxy binary at prefix %s',
                          self.install_prefix)
            return None


    def _create_symlink_qemu(self):
        """
        Create symbolic links for qemu and qemu-img commands on test bindir

        @return: None
        """
        logging.debug("Linking QEMU binaries")

        qemu_dst = os.path.join(self.test_bindir, self.QEMU_BIN)
        qemu_img_dst = os.path.join(self.test_bindir, self.QEMU_IMG_BIN)
        qemu_io_dst = os.path.join(self.test_bindir, self.QEMU_IO_BIN)
        qemu_fs_proxy_dst = os.path.join(self.test_bindir,
                                         self.QEMU_FS_PROXY_BIN)

        qemu_bin = self._qemu_bin_exists_at_prefix()
        if qemu_bin is not None:
            os.symlink(qemu_bin, qemu_dst)
        else:
            raise error.TestError('Invalid qemu path')

        qemu_img_bin = self._qemu_img_bin_exists_at_prefix()
        if qemu_img_bin is not None:
            os.symlink(qemu_img_bin, qemu_img_dst)
        else:
            raise error.TestError('Invalid qemu-img path')

        qemu_io_bin = self._qemu_io_bin_exists_at_prefix()
        if qemu_io_bin is not None:
            os.symlink(qemu_io_bin, qemu_io_dst)
        else:
            raise error.TestError('Invalid qemu-io path')

        qemu_fs_proxy_bin = self._qemu_fs_proxy_bin_exists_at_prefix()
        if qemu_fs_proxy_bin is not None:
            os.symlink(qemu_fs_proxy_bin, qemu_fs_proxy_dst)
        else:
            raise error.TestError('Invalid qemu fs proxy path')


    def _install_phase_init(self):
        '''
        Initializes the built and installed software

        This uses a simple mechanism of looking up the installer name
        for deciding what action to do.

        @return: None
        '''
        if 'unit' in self.name:
            self._cleanup_link_unittest()
            self._create_symlink_unittest()

        elif 'qemu' in self.name:
            self._cleanup_links_qemu()
            self._create_symlink_qemu()


    def uninstall(self):
        '''
        Performs the uninstallation of KVM userspace component

        @return: None
        '''
        self._kill_qemu_processes()
        self._cleanup_links()
        super(KVMBaseInstaller, self).uninstall()


class GitRepoInstaller(KVMBaseInstaller,
                       base_installer.GitRepoInstaller):
    '''
    Installer that deals with source code on Git repositories
    '''
    pass


class LocalSourceDirInstaller(KVMBaseInstaller,
                              base_installer.LocalSourceDirInstaller):
    '''
    Installer that deals with source code on local directories
    '''
    pass


class LocalSourceTarInstaller(KVMBaseInstaller,
                              base_installer.LocalSourceTarInstaller):
    '''
    Installer that deals with source code on local tarballs
    '''
    pass


class RemoteSourceTarInstaller(KVMBaseInstaller,
                               base_installer.RemoteSourceTarInstaller):
    '''
    Installer that deals with source code on remote tarballs
    '''
    pass
