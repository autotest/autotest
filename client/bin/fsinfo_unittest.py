#!/usr/bin/python

import unittest, StringIO
import common
from autotest_lib.client.bin import fsinfo
from autotest_lib.client.common_lib.test_utils import mock

class fsionfo_test(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(fsinfo, 'open')


    def tearDown(self):
        self.god.unstub_all()


    def create_test_file(self, filename, contents):
        test_file = StringIO.StringIO(contents)
        fsinfo.open.expect_call(filename, 'r').and_return(test_file)


    def test_ext_mkfs_options(self):
        tune2fs_dict = {'Filesystem volume name': '<none>',
                        'Last mounted on': '<not available>',
                        'Filesystem revision #': '1 (dynamic)',
                        'Block size': 4096,
                        'Block count': 263056,
                        'Fragment size': 4096,
                        'Blocks per group': 32768,
                        'Journal inode': 8,
                        'Reserved block count': 2630,
                        'Inode count': 131616,
                        'Filesystem features': 'filetype sparse_super',
                        'Filesystem OS type': 'Linux'}
        expected_option = {'-b': 4096,
                           '-f': 4096,
                           '-g': 32768,
                           '-j': None,
                           '-m': 1,
                           '-O': 'filetype,sparse_super',
                           '-o': 'Linux',
                           '-r': '1'}

        mkfs_option = {}
        fsinfo.ext_mkfs_options(tune2fs_dict, mkfs_option)

        for option, value in expected_option.iteritems():
            self.assertEqual(value, mkfs_option[option])


    def test_xfs_mkfs_options(self):
        tune2fs_dict = {'meta-data: isize': 256,
                        'meta-data: agcount': 8,
                        'meta-data: agsize': 32882,
                        'meta-data: sectsz': 512,
                        'meta-data: attr': 0,
                        'data: bsize': 4096,
                        'data: imaxpct': 25,
                        'data: sunit': 0,
                        'data: swidth': 0,
                        'data: unwritten': 1,
                        'naming: version': 2,
                        'naming: bsize': 4096,
                        'log: version': 1,
                        'log: sectsz': 512,
                        'log: sunit': 0,
                        'log: lazy-count': 0,
                        'log: bsize': 4096,
                        'log: blocks': 2560,
                        'realtime: extsz': 4096,
                        'realtime: blocks': 0,
                        'realtime: rtextents': 0}

        expected_option = {'-i size': 256,
                           '-d agcount': 8,
                           '-s size': 512,
                           '-b size': 4096,
                           '-i attr': 0,
                           '-i maxpct': 25,
                           '-d sunit': 0,
                           '-d swidth': 0,
                           '-d unwritten': 1,
                           '-n version': 2,
                           '-n size': 4096,
                           '-l version': 1,
                           '-l sectsize': 512,
                           '-l sunit': 0,
                           '-l lazy-count': 0,
                           '-r extsize': 4096,
                           '-r size': 0,
                           '-r rtdev': 0,
                           '-l size': 10485760}
        mkfs_option = {}
        fsinfo.xfs_mkfs_options(tune2fs_dict, mkfs_option)
        for option, value in expected_option.iteritems():
            self.assertEqual(value, mkfs_option[option])


    def test_opt_string2dict(self):
        test_string = '-q -b 1234   -O fdasfa,fdasfdas -l adfas -k -L'
        result = fsinfo.opt_string2dict(test_string)
        expected_result = {'-q': None,
                           '-b': 1234,
                           '-O': 'fdasfa,fdasfdas',
                           '-l': 'adfas',
                           '-k': None,
                           '-L': None}
        self.assertEqual(expected_result, result)


    def test_merge_ext_features(self):
        conf = 'a,b,d,d,d,d,d,e,e,a,f'.split(',')
        user = '^e,a,^f,g,h,i'
        expected_result = ['a', 'b', 'd', 'g', 'h', 'i']
        result = fsinfo.merge_ext_features(conf, user)
        self.assertEqual(expected_result, result)


    def test_compare_features(self):
        f1 = ['sparse_super', 'filetype', 'resize_inode', 'dir_index']
        f2 = ['filetype', 'resize_inode', 'dir_index', 'large_file']
        self.assertTrue(fsinfo.compare_features(f1, f1))
        self.assertFalse(fsinfo.compare_features(f1, f2))


    def test_mke2fs_conf(self):
        content = ('[defaults]\n'
                   'base_features = sparse_super,filetype,resize_inode\n'
                   '       blocksize = 4096 \n'
                   '       inode_ratio = 8192  \n'
                   '\n [fs_types]\n'
                   '       small = {\n'
                   '                         blocksize = 1024\n'
                   '               inode_ratio = 4096 \n'
                   '                                                 }\n'
                   '       floppy = {\n'
                   '                         blocksize = 4096\n'
                   '                                }\n')
        self.create_test_file('/etc/mke2fs.conf', content)

        conf_opt = fsinfo.parse_mke2fs_conf('small')
        mkfs_opt = fsinfo.convert_conf_opt(conf_opt)
        expected_conf = {'blocksize': 1024,
                         'inode_ratio': 4096,
                         'base_features': 'sparse_super,filetype,resize_inode'}
        expected_mkfs = {'-O': ['sparse_super', 'filetype', 'resize_inode'],
                         '-i': 4096,
                         '-b': 1024}
        self.assertEqual(conf_opt, expected_conf)
        self.assertEqual(mkfs_opt, expected_mkfs)


if __name__ == '__main__':
    unittest.main()
