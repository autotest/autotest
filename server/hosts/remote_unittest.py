#!/usr/bin/python

import unittest
import common

from autotest_lib.server.hosts import remote


class test_remote_host(unittest.TestCase):
    def test_has_hostname(self):
        host = remote.RemoteHost("myhost")
        self.assertEqual(host.hostname, "myhost")


if __name__ == "__main__":
    unittest.main()
