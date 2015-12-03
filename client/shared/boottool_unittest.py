#!/usr/bin/python

import logging
import os
import sys
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared.test_utils import mock
from autotest.client.shared import boottool
from autotest.client.tools import boottool as boot_tool


class TestEfiSys(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()

    def tearDown(self):
        self.god.unstub_all()

    def test_efi_path_not_found(self):
        self.god.stub_function(os.path, 'exists')
        self.god.stub_function(sys, 'exit')
        os.path.exists.expect_call('/sys/firmware/efi/vars').and_return(False)
        sys.exit.expect_call(-1)

        # Run
        self.efi_tool = boot_tool.EfiToolSys()
        self.god.check_playback()


class TestBoottool(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        # creates a bootloader with _run_boottool mocked out
        self.bt_mock = boottool.boottool()
        self.god.stub_function(self.bt_mock, '_run_grubby_get_return')
        self.god.stub_function(self.bt_mock, '_run_grubby_get_output')
        self.god.stub_function(self.bt_mock, '_run_get_output_err')
        self.god.stub_function(self.bt_mock, '_get_entry_selection')
        self.god.stub_function(self.bt_mock, 'get_info')
        self.god.stub_function(self.bt_mock, 'get_info_lines')

    def tearDown(self):
        self.god.unstub_all()

    def test_get_bootloader(self):
        # set up the recording
        args = [self.bt_mock.path, '--bootloader-probe']
        self.bt_mock._run_get_output_err.expect_call(args).and_return('lilo')
        # run the test
        self.assertEquals(self.bt_mock.get_bootloader(), 'lilo')
        self.god.check_playback()

    def test_get_architecture(self):
        self.god.stub_function(os, 'uname')
        # set up the recording
        os.uname.expect_call().and_return(('Linux', 'foobar.local',
                                           '3.2.7-1.fc16.x86_64',
                                           '#1 SMP Tue Feb 21 01:40:47 UTC 2012',
                                           'x86_64'))
        # run the test
        self.assertEquals(self.bt_mock.get_architecture(), 'x86_64')
        self.god.check_playback()

    def test_get_default_index(self):
        # set up the recording
        self.bt_mock._run_grubby_get_output.expect_call(['--default-index']).and_return(0)
        # run the test
        self.assertEquals(self.bt_mock.get_default_index(), 0)
        self.god.check_playback()

    def test_get_titles(self):
        # set up the recording
        output = ['index=0', 'title=title #1', 'index=1', 'title=title #2']
        self.bt_mock.get_info_lines.expect_call().and_return(output)
        # run the test
        self.assertEquals(self.bt_mock.get_titles(),
                          ['title #1', 'title #2'])
        self.god.check_playback()

    def test_get_entry(self):
        index = 5
        RESULT = ("""
index=%s
title="Fedora 16, kernel 3.2.6-3"
kernel=/vmlinuz-3.2.6-3.fc16.x86_64
args="ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"
root=/dev/mapper/vg_foo-lv_root
initrd=/boot/initramfs-3.2.6-3.fc16.x86_64.img
""" % index)
        # set up the recording
        self.bt_mock.get_info.expect_call(index).and_return(RESULT)
        actual_info = self.bt_mock.get_entry(index)
        expected_info = {'index': index,
                         'args': '"ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"',
                         'initrd': '/boot/initramfs-3.2.6-3.fc16.x86_64.img',
                         'kernel': '/vmlinuz-3.2.6-3.fc16.x86_64',
                         'root': '/dev/mapper/vg_foo-lv_root',
                         'title': '"Fedora 16, kernel 3.2.6-3"'}
        self.assertEquals(expected_info, actual_info)

    def test_get_entry_missing_result(self):
        index = 4
        RESULT = """
"""
        # set up the recording
        self.bt_mock.get_info.expect_call(index).and_return(RESULT)
        actual_info = self.bt_mock.get_entry(index)
        expected_info = {}
        self.assertEquals(expected_info, actual_info)

    def test_get_entries(self):
        self.god.stub_function(self.bt_mock, '_get_entry_indexes')
        entry_0 = '''
index=0
kernel=/vmlinuz-3.2.9-1.fc16.x86_64
args="ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"
root=/dev/mapper/vg_freedom-lv_root
initrd=/boot/initramfs-3.2.9-1.fc16.x86_64.img
'''
        entry_1 = '''
index=1
kernel=/vmlinuz-3.2.7-1.fc16.x86_64
args="ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"
root=/dev/mapper/vg_freedom-lv_root
initrd=/boot/initramfs-3.2.7-1.fc16.x86_64.img
'''
        entry_2 = '''
index=2
kernel=/vmlinuz-3.2.6-3.fc16.x86_64
args="ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"
root=/dev/mapper/vg_freedom-lv_root
initrd=/boot/initramfs-3.2.6-3.fc16.x86_64.img
'''
        RESULT = entry_0 + entry_1 + entry_2
        entry_indexes = [0, 1, 2]
        # run the test
        self.bt_mock.get_info.expect_call().and_return(RESULT)

        actual_info = self.bt_mock.get_entries()
        expected_info = {0: {'args': '"ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"',
                             'index': 0,
                             'initrd': '/boot/initramfs-3.2.9-1.fc16.x86_64.img',
                             'kernel': '/vmlinuz-3.2.9-1.fc16.x86_64',
                             'root': '/dev/mapper/vg_freedom-lv_root'},
                         1: {'args': '"ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"',
                             'index': 1,
                             'initrd': '/boot/initramfs-3.2.7-1.fc16.x86_64.img',
                             'kernel': '/vmlinuz-3.2.7-1.fc16.x86_64',
                             'root': '/dev/mapper/vg_freedom-lv_root'},
                         2: {'args': '"ro quiet rhgb SYSFONT=latarcyrheb-sun16 LANG=en_US.UTF-8 KEYTABLE=us-acentos"',
                             'index': 2,
                             'initrd': '/boot/initramfs-3.2.6-3.fc16.x86_64.img',
                             'kernel': '/vmlinuz-3.2.6-3.fc16.x86_64',
                             'root': '/dev/mapper/vg_freedom-lv_root'}}

        self.assertEquals(expected_info, actual_info)

        self.god.check_playback()

    def test_set_default(self):
        pass

    def test_add_args(self):
        # set up the recording
        kernel = 10
        args = "some kernel args"
        self.bt_mock._get_entry_selection.expect_call(kernel).and_return(kernel)
        command_arguments = ['--update-kernel=%s' % kernel,
                             '--args=%s' % args]
        self.bt_mock._run_grubby_get_return.expect_call(command_arguments)
        # run the test
        self.bt_mock.add_args(kernel, args)
        self.god.check_playback()

    def test_remove_args(self):
        # set up the recording
        kernel = 12
        args = "some kernel args"
        self.bt_mock._get_entry_selection.expect_call(kernel).and_return(kernel)
        command_arguments = ['--update-kernel=%s' % kernel,
                             '--remove-args=%s' % args]
        self.bt_mock._run_grubby_get_return.expect_call(command_arguments)
        # run the test
        self.bt_mock.remove_args(kernel, args)
        self.god.check_playback()

    def setup_add_kernel(self, oldtitle, path, title, root=None, args=None,
                         initrd=None, default=False, position='end'):
        self.bt_mock.get_titles = self.god.create_mock_function('get_titles')
        self.bt_mock.remove_kernel = self.god.create_mock_function('remove_kernel')

        # set up the recording
        self.bt_mock.get_titles.expect_call().and_return([oldtitle])
        if oldtitle == title:
            self.bt_mock.remove_kernel.expect_call(title)

        parameters = ['--add-kernel=%s' % path, '--title=%s' % title]
        # FIXME: grubby takes no --root parameter
        # if root:
        #    parameters.append('--root=%s' % root)
        if args:
            parameters.append('--args=%s' %
                              self.bt_mock._remove_duplicate_cmdline_args(args))
        if initrd:
            parameters.append('--initrd=%s' % initrd)
        if default:
            parameters.append('--make-default')

        # There's currently an issue with grubby '--add-to-bottom' feature.
        # Because it uses the tail instead of the head of the list to add
        # a new entry, when copying a default entry as a template
        # (--copy-default), it usually copies the "recover" entries that
        # usually go along a regular boot entry, specially on grub2.
        #
        # So, for now, until I fix grubby, we'll *not* respect the position
        # (--position=end) command line option.

        # if position:
        #    parameters.append('--position=%s' % position)
        parameters.append("--copy-default")
        self.bt_mock._run_grubby_get_return.expect_call(parameters)

    def test_add_kernel_basic(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel')
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel')
        self.god.check_playback()

    def test_add_kernel_removes_old(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='mylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel')
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel')
        self.god.check_playback()

    def test_add_kernel_adds_root(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel',
                              root='/unittest/root')
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel', root='/unittest/root')
        self.god.check_playback()

    def test_add_kernel_adds_args(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel',
                              args='my kernel args')
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel', args='my kernel args')
        self.god.check_playback()

    def test_add_kernel_args_remove_duplicates(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel',
                              args='param2 param1')
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel', args='param1 param2 param1')
        self.god.check_playback()

    def test_add_kernel_adds_initrd(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel',
                              initrd='/unittest/initrd')
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel', initrd='/unittest/initrd')
        self.god.check_playback()

    def test_add_kernel_enables_make_default(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel',
                              default=True)
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel', default=True)
        self.god.check_playback()

    def test_add_kernel_position(self):
        # set up the recording
        self.setup_add_kernel(oldtitle='notmylabel',
                              path='/unittest/kernels/vmlinuz', title='mylabel',
                              position=5)
        # run the test
        self.bt_mock.add_kernel(path='/unittest/kernels/vmlinuz',
                                title='mylabel', position=5)
        self.god.check_playback()

    def test_remove_kernel(self):
        index = 14
        # set up the recording
        self.bt_mock._get_entry_selection.expect_call(index).and_return(index)
        command_arguments = ['--remove-kernel=%s' % index]
        self.bt_mock._run_grubby_get_return.expect_call(command_arguments)
        # run the test
        self.bt_mock.remove_kernel(index)
        self.god.check_playback()

    def test_boot_once(self):
        self.god.stub_function(self.bt_mock, 'get_bootloader')
        self.god.stub_function(self.bt_mock, '_index_for_title')
        self.god.stub_function(self.bt_mock, 'get_default_title')
        self.god.stub_function(boottool, 'install_grubby_if_missing')
        # set up the recording
        title = 'autotest'
        entry_index = 1
        default_title = 'linux'
        default_index = 0
        info_lines = ['index=%s' % default_index, 'title=%s' % default_title,
                      'index=%s' % entry_index, 'title=%s' % title]
        bootloaders = ('grub2', 'grub', 'yaboot', 'elilo')
        for bootloader in bootloaders:
            self.god.stub_function(self.bt_mock, 'boot_once_%s' % bootloader)
            self.god.stub_function(self.bt_mock, '_init_on_demand')
            self.bt_mock.log = logging
            self.bt_mock.get_info_lines.expect_call().and_return(info_lines)
            self.bt_mock.get_default_title.expect_call().and_return(default_title)
            self.bt_mock.get_bootloader.expect_call().and_return(bootloader)
            if bootloader in ('grub', 'grub2', 'elilo'):
                self.bt_mock._index_for_title.expect_call(title).and_return(entry_index)
            bootloader_func = getattr(self.bt_mock, 'boot_once_%s' % bootloader)
            if bootloader in ('yaboot'):
                arg = title
            else:
                arg = entry_index
            bootloader_func.expect_call(arg)
            # run the test
            self.bt_mock.boot_once('autotest')
            self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
