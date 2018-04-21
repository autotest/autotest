#!/usr/bin/env python

#  Copyright(c) 2013 Intel Corporation.
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms and conditions of the GNU General Public License,
#  version 2, as published by the Free Software Foundation.
#
#  This program is distributed in the hope it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
#
#  The full GNU General Public License is included in this distribution in
#  the file called "COPYING".

import pickle
import sys
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import backports
from autotest.client.shared.backports.collections import namedtuple


# Used in namedtuple unittests, put at module scope to cope with pickle:
# "classes that are defined at the top level of a module"
Point = namedtuple('Point', 'x, y')


class TestBackports(unittest.TestCase):

    def test_any(self):
        self.assertTrue(backports.any([False, 0, 1, "", True, set()]))
        self.assertFalse(backports.any([]))
        self.assertFalse(backports.any(set()))
        self.assertFalse(backports.any(["", 0, False]))

    def test_all(self):
        self.assertFalse(backports.all([False, 0, 1, "", True]))
        self.assertTrue(backports.all([]))
        self.assertFalse(backports.all(["", 0, False, set()]))
        self.assertTrue(backports.all(["True", 1, True]))

    def test_bin(self):
        self.assertEquals(backports.bin(170), '0b10101010')

    def test_many_bin(self):
        try:
            for n in range(10000):
                # pylint: disable=E0602
                self.assertEquals(backports.bin(n), bin(n))
            # pylint: disable=E0602
            self.assertEquals(backports.bin(sys.maxint), bin(sys.maxint))
        except NameError:
            # NameError will occur on Python versions that lack bin()
            pass

    def test_next(self):
        self.assertEquals(backports.next((x * 2 for x in range(3, 5))), 6)
        self.assertEquals(backports.next((x * 2 for x in range(3, 5) if x > 100),
                                         "default"), "default")

    def test_next_extra_arg(self):
        @staticmethod
        def _fail_extra_arg():
            backports.next((x * 2 for x in range(3, 5) if x > 100),
                           ("default", "extra arg"))
        self.assertRaises(TypeError, _fail_extra_arg)

    def test_namedtuple_pickle(self):
        '''
        Verify that instances can be pickled
        '''
        p = Point(x=10, y=20)
        self.assertEquals(p, pickle.loads(pickle.dumps(p, -1)))

    def test_namedtuple_override(self):
        '''
        Test and demonstrate ability to override methods
        '''
        class HypotPoint(namedtuple('Point', 'x y')):

            @property
            def hypot(self):
                return (self.x ** 2 + self.y ** 2) ** 0.5

            def __str__(self):
                return 'Point: x=%6.3f y=%6.3f hypot=%6.3f' % (self.x,
                                                               self.y,
                                                               self.hypot)
        p1 = HypotPoint(3, 4)
        p2 = HypotPoint(14, 5)
        p3 = HypotPoint(9. / 7, 6)
        self.assertEquals(p1.hypot, 5.0)
        self.assertAlmostEquals(p2.hypot, 14.866068747318506)
        self.assertAlmostEquals(p3.hypot, 6.136209027118437)

    def test_namedtuple_optimize(self):
        """
        Tests a point class with optimized _make() and _replace()

        The optimized versions have no error-checking
        """
        class OptimizedPoint(namedtuple('Point', 'x y')):
            _make = classmethod(tuple.__new__)

            def _replace(self, _map=map, **kwds):
                return self._make(_map(kwds.get, ('x', 'y'), self))

        p = OptimizedPoint(11, 22)._replace(x=100)
        self.assertEquals(p.x, 100)


if __name__ == '__main__':
    unittest.main()
