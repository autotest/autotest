#!/usr/bin/env python
import unittest

from autotest.client import base_utils


class TestLsmod(unittest.TestCase):

    LSMOD_OUT = """\
Module                  Size  Used by
ccm                    17773  2
ip6t_rpfilter          12546  1
ip6t_REJECT            12939  2
xt_conntrack           12760  9
ebtable_nat            12807  0
ebtable_broute         12731  0
bridge                110862  1 ebtable_broute
stp                    12868  1 bridge
llc                    13941  2 stp,bridge
ebtable_filter         12827  0
ebtables               30758  3 ebtable_broute,ebtable_nat,ebtable_filter
ip6table_nat           13015  1
nf_conntrack_ipv6      18738  6
nf_defrag_ipv6         34712  1 nf_conntrack_ipv6
nf_nat_ipv6            13213  1 ip6table_nat
ip6table_mangle        12700  1
ip6table_security      12710  1
ip6table_raw           12683  1
ip6table_filter        12815  1
"""

    def test_parse_lsmod(self):
        lsmod_info = base_utils.parse_lsmod_for_module(
            self.LSMOD_OUT, "ebtables")
        submodules = ['ebtable_broute', 'ebtable_nat', 'ebtable_filter']
        assert lsmod_info['submodules'] == submodules
        assert lsmod_info == {
            'name': "ebtables",
            'size': 30758,
            'used': 3,
            'submodules': submodules
        }

    @staticmethod
    def test_parse_lsmod_is_empty():
        lsmod_info = base_utils.parse_lsmod_for_module("", "ebtables")
        assert lsmod_info == {}

    def test_parse_lsmod_no_submodules(self):
        lsmod_info = base_utils.parse_lsmod_for_module(self.LSMOD_OUT, "ccm")
        submodules = []
        assert lsmod_info['submodules'] == submodules
        assert lsmod_info == {
            'name': "ccm",
            'size': 17773,
            'used': 2,
            'submodules': submodules
        }

    def test_parse_lsmod_single_submodules(self):
        lsmod_info = base_utils.parse_lsmod_for_module(
            self.LSMOD_OUT, "bridge")
        submodules = ['ebtable_broute']
        assert lsmod_info['submodules'] == submodules
        assert lsmod_info == {
            'name': "bridge",
            'size': 110862,
            'used': 1,
            'submodules': submodules
        }


if __name__ == '__main__':
    unittest.main()
