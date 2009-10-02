#!/usr/bin/python

import unittest
import common

from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import boottool


class test_boottool(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        # creates a bootloader with _run_boottool mocked out
        self.bt_mock = boottool.boottool()
        self.god.stub_function(self.bt_mock, '_run_boottool')


    def tearDown(self):
        self.god.unstub_all()


    def expect_run_boottool(self, args, result=''):
        self.bt_mock._run_boottool.expect_call(*args).and_return(result)


    def test_get_type(self):
        # set up the recording
        self.expect_run_boottool(('--bootloader-probe',), 'lilo\n')
        # run the test
        self.assertEquals(self.bt_mock.get_type(), 'lilo')
        self.god.check_playback()


    def test_get_arch(self):
        # set up the recording
        self.expect_run_boottool(('--arch-probe',), 'x86_64\n')
        # run the test
        self.assertEquals(self.bt_mock.get_architecture(), 'x86_64')
        self.god.check_playback()


    def test_get_default(self):
        # set up the recording
        self.expect_run_boottool(('--default',), '0\n')
        # run the test
        self.assertEquals(self.bt_mock.get_default(), 0)
        self.god.check_playback()


    def test_get_titles(self):
        # set up the recording
        self.expect_run_boottool(
                ('--info=all',), '\nindex\t: 0\ntitle\t: title #1\n'
                '\nindex\t: 1\ntitle\t: title #2\n')
        # run the test
        self.assertEquals(self.bt_mock.get_titles(),
                          ['title #1', 'title #2'])
        self.god.check_playback()


    def test_get_entry(self):
        RESULT = (
        'index\t: 5\n'
        'args\t: ro single\n'
        'boot\t: (hd0,0)\n'
        'initrd\t: /boot/initrd.img-2.6.15-23-386\n'
        'kernel\t: /boot/vmlinuz-2.6.15-23-386\n'
        'root\t: UUID=07D7-0714\n'
        'savedefault\t:   \n'
        'title\t: Distro, kernel 2.6.15-23-386\n'
        )
        # set up the recording
        self.expect_run_boottool(('--info=5',), RESULT)
        # run the test
        info = self.bt_mock.get_entry(5)
        self.god.check_playback()
        expected_info = {'index': 5, 'args': 'ro single',
                         'boot': '(hd0,0)',
                         'initrd': '/boot/initrd.img-2.6.15-23-386',
                         'kernel': '/boot/vmlinuz-2.6.15-23-386',
                         'root': 'UUID=07D7-0714', 'savedefault': '',
                         'title': 'Distro, kernel 2.6.15-23-386'}
        self.assertEquals(expected_info, info)


    def test_get_entry_missing_result(self):
        # set up the recording
        self.expect_run_boottool(('--info=4',), '')
        # run the test
        info = self.bt_mock.get_entry(4)
        self.god.check_playback()
        self.assertEquals({}, info)


    def test_get_entries(self):
        RESULT = (
        'index\t: 5\n'
        'args\t: ro single\n'
        'boot\t: (hd0,0)\n'
        'initrd\t: /boot/initrd.img-2.6.15-23-386\n'
        'kernel\t: /boot/vmlinuz-2.6.15-23-386\n'
        'root\t: UUID=07D7-0714\n'
        'savedefault\t:   \n'
        'title\t: Distro, kernel 2.6.15-23-386\n'
        '\n'
        'index\t: 7\n'
        'args\t: ro single\n'
        'boot\t: (hd0,0)\n'
        'initrd\t: /boot/initrd.img-2.6.15-23-686\n'
        'kernel\t: /boot/vmlinuz-2.6.15-23-686\n'
        'root\t: UUID=07D7-0714\n'
        'savedefault\t:   \n'
        'title\t: Distro, kernel 2.6.15-23-686\n'
        )
        # set up the recording
        self.expect_run_boottool(('--info=all',), RESULT)
        # run the test
        info = self.bt_mock.get_entries()
        self.god.check_playback()
        expected_info = {
            5: {'index': 5, 'args': 'ro single', 'boot': '(hd0,0)',
                'initrd': '/boot/initrd.img-2.6.15-23-386',
                'kernel': '/boot/vmlinuz-2.6.15-23-386',
                'root': 'UUID=07D7-0714', 'savedefault': '',
                'title': 'Distro, kernel 2.6.15-23-386'},
            7: {'index': 7, 'args': 'ro single', 'boot': '(hd0,0)',
                'initrd': '/boot/initrd.img-2.6.15-23-686',
                'kernel': '/boot/vmlinuz-2.6.15-23-686',
                'root': 'UUID=07D7-0714', 'savedefault': '',
                'title': 'Distro, kernel 2.6.15-23-686'}}
        self.assertEquals(expected_info, info)


    def test_set_default(self):
        # set up the recording
        self.expect_run_boottool(('--set-default=41',))
        # run the test
        self.bt_mock.set_default(41)
        self.god.check_playback()


    def test_add_args(self):
        # set up the recording
        self.expect_run_boottool(
            ('--update-kernel=10', '--args=some kernel args'))
        # run the test
        self.bt_mock.add_args(10, 'some kernel args')
        self.god.check_playback()


    def test_remove_args(self):
        # set up the recording
        self.expect_run_boottool(
            ('--update-kernel=12', '--remove-args=some kernel args'))
        # run the test
        self.bt_mock.remove_args(12, 'some kernel args')
        self.god.check_playback()


    def setup_add_kernel(self, oldtitle, path, title, root=None, args=None,
                         initrd=None, default=False, position='end',
                         xen_hypervisor=None):
        self.bt_mock.get_titles = self.god.create_mock_function('get_titles')
        # set up the recording
        self.bt_mock.get_titles.expect_call().and_return([oldtitle])
        if oldtitle == title:
            self.expect_run_boottool(('--remove-kernel=%s' % oldtitle,))

        parameters = ['--add-kernel=%s' % path, '--title=%s' % title]
        if root:
            parameters.append('--root=%s' % root)
        if args:
            parameters.append('--args=%s' % args)
        if initrd:
            parameters.append('--initrd=%s' % initrd)
        if default:
            parameters.append('--make-default')
        if position:
            parameters.append('--position=%s' % position)
        if self.bt_mock.get_xen_mode():
            parameters.append('--xen')
            if xen_hypervisor:
                parameters.append('--xenhyper=%s' % xen_hypervisor)
        self.expect_run_boottool(parameters)


    def test_add_kernel_basic(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel')
        self.god.check_playback()


    def test_add_kernel_removes_old(self):
        # set up the recording
        self.setup_add_kernel(
                'mylabel', '/unittest/kernels/vmlinuz', 'mylabel')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz', 'mylabel')
        self.god.check_playback()


    def test_add_kernel_adds_root(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                root='/unittest/root')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', root='/unittest/root')
        self.god.check_playback()


    def test_add_kernel_adds_args(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                args='my kernel args')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', args='my kernel args')
        self.god.check_playback()


    def test_add_kernel_args_remove_duplicates(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                args='param2 param1')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', args='param1 param2 param1')
        self.god.check_playback()


    def test_add_kernel_adds_initrd(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                initrd='/unittest/initrd')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', initrd='/unittest/initrd')
        self.god.check_playback()


    def test_add_kernel_enables_make_default(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                default=True)
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', default=True)
        self.god.check_playback()


    def test_add_kernel_position(self):
        # set up the recording
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                position=5)
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', position=5)
        self.god.check_playback()


    def test_remove_kernel(self):
        # set up the recording
        self.expect_run_boottool(('--remove-kernel=14',))
        # run the test
        self.bt_mock.remove_kernel(14)
        self.god.check_playback()


    def test_boot_once(self):
        # set up the recording
        self.expect_run_boottool(('--boot-once', '--title=autotest'))
        # run the test
        self.bt_mock.boot_once('autotest')
        self.god.check_playback()


    def test_enable_xen(self):
        self.bt_mock.enable_xen_mode()
        self.assertTrue(self.bt_mock.get_xen_mode())


    def test_disable_xen(self):
        self.bt_mock.disable_xen_mode()
        self.assertFalse(self.bt_mock.get_xen_mode())


    def test_add_kernel_xen(self):
        # set up the recording
        self.bt_mock.enable_xen_mode()
        self.setup_add_kernel(
                'notmylabel', '/unittest/kernels/vmlinuz', 'mylabel',
                xen_hypervisor='xen_image')
        # run the test
        self.bt_mock.add_kernel('/unittest/kernels/vmlinuz',
                                'mylabel', xen_hypervisor='xen_image')
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
