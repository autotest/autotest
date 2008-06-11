#!/usr/bin/python

import unittest
import common

from autotest_lib.server.hosts import remote


class test_remote_host(unittest.TestCase):
    def test_has_hostname(self):
        host = remote.RemoteHost()
        self.assertTrue(hasattr(host, "hostname"))


    def test_is_site_host_subclass(self):
        try:
            from autotest_lib.server.hosts import site_host
        except ImportError:
            pass
        else:
            self.assertTrue(issubclass(remote.RemoteHost, site_host.SiteHost))


if __name__ == "__main__":
    unittest.main()
