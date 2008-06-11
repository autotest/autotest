#!/usr/bin/python
import unittest
import common
from autotest_lib.client.bin import kernel_versions


class kernel_versions_test(unittest.TestCase):

    def increases(self, kernels):
        for i in xrange(len(kernels)-1):
            k1 = kernels[i]
            k2 = kernels[i+1]
            ek1 = kernel_versions.version_encode(k1)
            ek2 = kernel_versions.version_encode(k2)
            self.assertTrue(ek1 < ek2,
                    '%s (-> %s)  should sort <  %s (-> %s)'
                    % (k1, ek1, k2, ek2) )


    def test_version_encode(self):
        series1 = [
                '2.6',
                '2.6.0',
                '2.6.1-rc1',
                '2.6.1-rc1_fix',
                '2.6.1-rc1_patch',
                '2.6.1-rc9',
                '2.6.1-rc9-mm1',
                '2.6.1-rc9-mm2',
                '2.6.1-rc10',
                '2.6.1-rc98',
                '2.6.1',
                '2.6.1_patch',
                '2.6.9',
                '2.6.10',
                '2.6.99',
                '2.7',
                '2.9.99',
                '2.10.0',
                '99.99.99',
                'UNKNOWN',
                ]
        self.increases(series1)
        self.increases(['pathX'+k for k in series1])
        series2 = [
                '2.6.18-smp-220',
                '2.6.18-smp-220.0',
                '2.6.18-smp-220.1_rc1',
                '2.6.18-smp-220.1_rc1_fix',
                '2.6.18-smp-220.1_rc1_patch',
                '2.6.18-smp-220.1_rc9',
                '2.6.18-smp-220.1_rc9_mm1',
                '2.6.18-smp-220.1_rc9_mm2',
                '2.6.18-smp-220.1_rc10',
                '2.6.18-smp-220.1_rc98',
                '2.6.18-smp-220.1',
                '2.6.18-smp-220.1_patch',
                '2.6.18-smp-220.9',
                '2.6.18-smp-220.10',
                '2.6.18-smp-220.99',
                '2.6.18-smp-221',
                'UNKNOWN',
                ]
        self.increases(series2)
        self.increases(['pathX'+k for k in series2])


    releases    = ['2.6.1'      , '2.6.18-smp-220.0'   ]
    candidates  = ['2.6.1-rc1'  , '2.6.18-smp-220.0_rc1']
    experiments = ['2.6.1-patch', '2.6.1-rc1_patch', '2.6.18-smp-220.0_patch',
                   'UNKNOWN']

    def test_is_released_kernel(self):
        for v in self.releases:
            self.assertTrue(kernel_versions.is_released_kernel(v))
        for v in self.candidates + self.experiments:
            self.assertFalse(kernel_versions.is_released_kernel(v))


    def test_is_release_candidate(self):
        for v in self.releases + self.candidates:
            self.assertTrue(kernel_versions.is_release_candidate(v))
        for v in self.experiments:
            self.assertFalse(kernel_versions.is_release_candidate(v))


if  __name__ == "__main__":
    unittest.main()
