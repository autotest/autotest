#!/usr/bin/python

import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from kernelexpand import decompose_kernel
from kernelexpand import mirror_kernel_components
from autotest.client.shared.settings import settings
from autotest.client.shared.test_utils import mock

km = 'http://www.kernel.org/pub/linux/kernel/'
akpm = km + 'people/akpm/patches/'
gw = 'http://git.kernel.org/?p=linux/kernel/git/torvalds/linux.git'
sgw = 'http://git.kernel.org/?p=linux/kernel/git/stable/linux-stable.git'

kml = 'http://www.example.com/mirror/kernel.org/'
akpml = 'http://www.example.com/mirror/akpm/'

mirrorA = [
    [akpm, akpml],
    [km, kml],
]


class kernelexpandTest(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        settings.override_value('CLIENT', 'kernel_mirror', km)
        settings.override_value('CLIENT', 'kernel_gitweb', '')
        settings.override_value('CLIENT', 'stable_kernel_gitweb', '')

    def tearDown(self):
        self.god.unstub_all()

    def test_decompose_simple(self):
        correct = [[km + 'v2.6/linux-2.6.23.tar.bz2']]
        sample = decompose_kernel('2.6.23')
        self.assertEqual(sample, correct)

    def test_decompose_simple_30(self):
        correct = [[km + 'v3.x/linux-3.0.14.tar.bz2', km + 'v3.x/linux-3.0.14.tar.xz']]
        sample = decompose_kernel('3.0.14')
        self.assertEqual(sample, correct)

    def test_decompose_simple_3X(self):
        correct = [[km + 'v3.x/linux-3.2.1.tar.bz2', km + 'v3.x/linux-3.2.1.tar.xz']]
        sample = decompose_kernel('3.2.1')
        self.assertEqual(sample, correct)

    def test_decompose_nominor_30(self):
        correct = [[km + 'v3.x/linux-3.0.tar.bz2', km + 'v3.x/linux-3.0.tar.xz']]
        sample = decompose_kernel('3.0')
        self.assertEqual(sample, correct)

    def test_decompose_nominor_26_fail(self):
        success = False
        try:
            sample = decompose_kernel('2.6')
            success = True
        except NameError:
            pass
        except Exception as e:
            self.fail('expected NameError, got something else')

        if success:
            self.fail('expected NameError, was successful')

    def test_decompose_testing_26(self):
        correct = km + 'v2.6/testing/linux-2.6.35-rc1.tar.bz2'
        sample = decompose_kernel('2.6.35-rc1')[0][1]
        self.assertEqual(sample, correct)

    def test_decompose_testing_30(self):
        correct = km + 'v3.x/testing/linux-3.2-rc1.tar.bz2'
        sample = decompose_kernel('3.2-rc1')[0][0]
        self.assertEqual(sample, correct)

    def test_decompose_testing_30_fail(self):
        success = False
        try:
            sample = decompose_kernel('3.2.1-rc1')
            success = True
        except NameError:
            pass
        except Exception as e:
            self.fail('expected NameError, got something else')

        if success:
            self.fail('expected NameError, was successful')

    def test_decompose_gitweb(self):
        settings.override_value('CLIENT', 'kernel_gitweb', gw)
        settings.override_value('CLIENT', 'stable_kernel_gitweb', sgw)
        correct = [[km + 'v3.x/linux-3.0.tar.bz2', km + 'v3.x/linux-3.0.tar.xz', gw + ';a=snapshot;h=refs/tags/v3.0;sf=tgz']]
        sample = decompose_kernel('3.0')
        self.assertEqual(sample, correct)

    def test_decompose_sha1(self):
        settings.override_value('CLIENT', 'kernel_gitweb', gw)
        settings.override_value('CLIENT', 'stable_kernel_gitweb', sgw)
        correct = [[gw + ';a=snapshot;h=02f8c6aee8df3cdc935e9bdd4f2d020306035dbe;sf=tgz', sgw + ';a=snapshot;h=02f8c6aee8df3cdc935e9bdd4f2d020306035dbe;sf=tgz']]
        sample = decompose_kernel('02f8c6aee8df3cdc935e9bdd4f2d020306035dbe')
        self.assertEqual(sample, correct)

    def test_decompose_fail(self):
        success = False
        try:
            sample = decompose_kernel('1.0.0.0.0')
            success = True
        except NameError:
            pass
        except Exception as e:
            self.fail('expected NameError, got something else')

        if success:
            self.fail('expected NameError, was successful')

    def test_decompose_rcN(self):
        correct = [
            [km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
                  km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2']
        ]
        sample = decompose_kernel('2.6.23-rc1')
        self.assertEqual(sample, correct)

    def test_decompose_mmN(self):
        correct = [
            [km + 'v2.6/linux-2.6.23.tar.bz2'],
            [akpm + '2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2']
        ]
        sample = decompose_kernel('2.6.23-mm1')
        self.assertEqual(sample, correct)

    def test_decompose_gitN(self):
        correct = [
            [km + 'v2.6/linux-2.6.23.tar.bz2'],
            [km + 'v2.6/snapshots/old/patch-2.6.23-git1.bz2',
                  km + 'v2.6/snapshots/patch-2.6.23-git1.bz2']
        ]
        sample = decompose_kernel('2.6.23-git1')
        self.assertEqual(sample, correct)

    def test_decompose_rcN_mmN(self):
        correct = [
            [km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
                  km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2'],
            [akpm + '2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2']
        ]
        sample = decompose_kernel('2.6.23-rc1-mm1')
        self.assertEqual(sample, correct)

    def test_mirrorA_simple(self):
        correct = [
            [kml + 'v2.6/linux-2.6.23.tar.bz2',
             km + 'v2.6/linux-2.6.23.tar.bz2']
        ]
        sample = decompose_kernel('2.6.23')
        sample = mirror_kernel_components(mirrorA, sample)

        self.assertEqual(sample, correct)

    def test_mirrorA_rcN(self):
        correct = [
            [kml + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
             kml + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2',
             km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
                  km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2']
        ]
        sample = decompose_kernel('2.6.23-rc1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)

    def test_mirrorA_mmN(self):
        correct = [
            [kml + 'v2.6/linux-2.6.23.tar.bz2',
             km + 'v2.6/linux-2.6.23.tar.bz2'],
            [akpml + '2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2',
             kml + 'people/akpm/patches/2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2',
             akpm + '2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2']
        ]

        sample = decompose_kernel('2.6.23-mm1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)

    def test_mirrorA_gitN(self):
        correct = [
            [kml + 'v2.6/linux-2.6.23.tar.bz2',
             km + 'v2.6/linux-2.6.23.tar.bz2'],
            [kml + 'v2.6/snapshots/old/patch-2.6.23-git1.bz2',
             kml + 'v2.6/snapshots/patch-2.6.23-git1.bz2',
             km + 'v2.6/snapshots/old/patch-2.6.23-git1.bz2',
                  km + 'v2.6/snapshots/patch-2.6.23-git1.bz2']
        ]
        sample = decompose_kernel('2.6.23-git1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)

    def test_mirrorA_rcN_mmN(self):
        correct = [
            [kml + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
             kml + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2',
             km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
                  km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2'],
            [akpml + '2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2',
             kml + 'people/akpm/patches/2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2',
             akpm + '2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2']
        ]
        sample = decompose_kernel('2.6.23-rc1-mm1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)


if __name__ == '__main__':
    unittest.main()
