#!/usr/bin/python

import unittest

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import xml_utils, ElementTree


class test_xml_utils(unittest.TestCase):

    def test_bundled_elementtree(self):
        self.assertEqual(xml_utils.ElementTree.VERSION, ElementTree.VERSION)


if __name__ == "__main__":
    unittest.main()
