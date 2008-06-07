#!/usr/bin/python

import unittest
from kernelexpand import decompose_kernel
from kernelexpand import mirror_kernel_components

km = 'http://www.kernel.org/pub/linux/kernel/'
akpm = km + 'people/akpm/patches/'

kml = 'http://www.example.com/mirror/kernel.org/'
akpml = 'http://www.example.com/mirror/akpm/'

mirrorA = [
        [ akpm, akpml ],
        [ km, kml ],
]

class kernelexpandTest(unittest.TestCase):
    def test_decompose_simple(self):
        correct = [ [ km + 'v2.6/linux-2.6.23.tar.bz2' ] ]
        sample = decompose_kernel('2.6.23')
        self.assertEqual(sample, correct)


    def test_decompose_fail(self):
        success = False
        try:
            sample = decompose_kernel('1.0.0.0.0')
            success = True
        except NameError:
            pass
        except Exception, e:
            self.fail('expected NameError, got something else')

        if success:
            self.fail('expected NameError, was successful')


    def test_decompose_rcN(self):
        correct = [
          [ km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
            km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2']
        ]
        sample = decompose_kernel('2.6.23-rc1')
        self.assertEqual(sample, correct)


    def test_decompose_mmN(self):
        correct = [
          [ km + 'v2.6/linux-2.6.23.tar.bz2' ],
          [ akpm + '2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2' ]
        ]
        sample = decompose_kernel('2.6.23-mm1')
        self.assertEqual(sample, correct)


    def test_decompose_gitN(self):
        correct = [
          [ km + 'v2.6/linux-2.6.23.tar.bz2' ],
          [ km + 'v2.6/snapshots/old/patch-2.6.23-git1.bz2',
            km + 'v2.6/snapshots/patch-2.6.23-git1.bz2']
        ]
        sample = decompose_kernel('2.6.23-git1')
        self.assertEqual(sample, correct)


    def test_decompose_rcN_mmN(self):
        correct = [
          [ km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
            km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2' ],
          [ akpm + '2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2']
        ]
        sample = decompose_kernel('2.6.23-rc1-mm1')
        self.assertEqual(sample, correct)


    def test_mirrorA_simple(self):
        correct = [
          [ kml + 'v2.6/linux-2.6.23.tar.bz2',
            km + 'v2.6/linux-2.6.23.tar.bz2' ]
        ]
        sample = decompose_kernel('2.6.23')
        sample = mirror_kernel_components(mirrorA, sample)

        self.assertEqual(sample, correct)


    def test_mirrorA_rcN(self):
        correct = [
          [ kml + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
            kml + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2',
            km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
            km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2' ]
        ]
        sample = decompose_kernel('2.6.23-rc1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)


    def test_mirrorA_mmN(self):
        correct = [
          [ kml + 'v2.6/linux-2.6.23.tar.bz2',
            km + 'v2.6/linux-2.6.23.tar.bz2'],
          [ akpml + '2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2',
            kml + 'people/akpm/patches/2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2',
            akpm + '2.6/2.6.23/2.6.23-mm1/2.6.23-mm1.bz2' ]
        ]

        sample = decompose_kernel('2.6.23-mm1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)


    def test_mirrorA_gitN(self):
        correct = [
          [ kml + 'v2.6/linux-2.6.23.tar.bz2',
            km + 'v2.6/linux-2.6.23.tar.bz2'],
          [ kml + 'v2.6/snapshots/old/patch-2.6.23-git1.bz2',
            kml + 'v2.6/snapshots/patch-2.6.23-git1.bz2',
            km + 'v2.6/snapshots/old/patch-2.6.23-git1.bz2',
            km + 'v2.6/snapshots/patch-2.6.23-git1.bz2' ]
        ]
        sample = decompose_kernel('2.6.23-git1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)


    def test_mirrorA_rcN_mmN(self):
        correct = [
          [ kml + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
            kml + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2',
            km + 'v2.6/testing/v2.6.23/linux-2.6.23-rc1.tar.bz2',
            km + 'v2.6/testing/linux-2.6.23-rc1.tar.bz2'],
          [ akpml + '2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2',
            kml + 'people/akpm/patches/2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2',
            akpm + '2.6/2.6.23-rc1/2.6.23-rc1-mm1/2.6.23-rc1-mm1.bz2' ]
        ]
        sample = decompose_kernel('2.6.23-rc1-mm1')
        sample = mirror_kernel_components(mirrorA, sample)
        self.assertEqual(sample, correct)


if __name__ == '__main__':
    unittest.main()
