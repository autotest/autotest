#!/usr/bin/python

__author__ = 'raphtee@google.com (Travis Miller)'

import unittest
import common
from autotest_lib.server import utils


class UtilsTest(unittest.TestCase):

    def setUp(self):
        # define out machines here
        self.machines = ['mach1', 'mach2', 'mach3', 'mach4', 'mach5',
                                'mach6', 'mach7']

        self.ntuples = [['mach1', 'mach2'], ['mach3', 'mach4'],
                        ['mach5', 'mach6']]
        self.failures = []
        self.failures.append(('mach7', "machine can not be tupled"))


    def test_form_cell_mappings(self):
        (ntuples, failures) = utils.form_ntuples_from_machines(self.machines)
        self.assertEquals(self.ntuples, ntuples)
        self.assertEquals(self.failures, failures)


if __name__ == "__main__":
    unittest.main()
