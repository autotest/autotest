#!/usr/bin/python

import unittest, os, time
import common
from autotest_lib.client.bin import net_utils, autotest_utils
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import utils, error


class TestNetUtils(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "system")
        self.god.stub_function(utils, "system_output")
        self.god.stub_function(autotest_utils, "module_is_loaded")
        self.god.stub_function(net_utils, "open")
        self.god.stub_function(time, 'sleep')


    def tearDown(self):
        self.god.unstub_all()


    def test_reset_network(self):
        utils.system.expect_call('service network restart')
        utils.system.expect_call('service tunekernel start')

        net_utils.reset_network()
        self.god.check_playback()


    def test_start_network(self):
        utils.system.expect_call('service network start')
        utils.system.expect_call('service tunekernel start')

        net_utils.start_network()
        self.god.check_playback()


    def test_enable_ip_loopback(self):
        msg = "echo '1' > /proc/sys/net/ipv4/route/no_local_loopback"
        utils.system.expect_call(msg)

        net_utils.enable_ip_loopback()
        self.god.check_playback()


    def test_disable_ip_loopback(self):
        msg = "echo '0' > /proc/sys/net/ipv4/route/no_local_loopback"
        utils.system.expect_call(msg)

        net_utils.disable_ip_loopback()
        self.god.check_playback()


    def test_bonding_is_enabled(self):
        autotest_utils.module_is_loaded.expect_call('bonding').and_return('ok')

        self.assertEquals(net_utils.bonding_is_enabled(), "ok")
        self.god.check_playback()


    def netif_setup(self):
        # setup
        os.environ['AUTODIR'] = "autodir"
        self.ethtool_exec =  os.path.join("autodir", 'tools', 'ethtool')
        self.name = 'eth0'

        #record
        ifconfig_output = "inet addr:127.0.0.1 Down"
        utils.system_output.expect_call('ifconfig %s'
                                        % self.name).and_return(ifconfig_output)
        utils.system_output.expect_call('ifconfig %s'
                                        % self.name).and_return(ifconfig_output)
        autotest_utils.module_is_loaded.expect_call('bonding').and_return(False)
        utils.system_output.expect_call('%s %s %s'
                   % (self.ethtool_exec, '-l', self.name)).and_return('enabled')


    def wait_for_carrier(self, num_trys=0):
        f = self.god.create_mock_class(file, "file")
        if num_trys == 0:
            net_utils.open.expect_call('/sys/class/net/%s/carrier'
                                       % self.name).and_return(f)
            f.read.expect_call().and_return('1')
            f.close.expect_call()
        else:
            for i in range(num_trys):
                net_utils.open.expect_call('/sys/class/net/%s/carrier'
                                           % self.name).and_return(f)
                f.read.expect_call().and_return('not yet')
                f.close.expect_call()
                time.sleep.expect_call(1)


    def test_enable_bonding(self):
        utils.system.expect_call('service network glag-enable',
                                 ignore_status=True)
        self.netif_setup()
        self.wait_for_carrier()

        # run test
        net_utils.enable_bonding()
        self.god.check_playback()


    def test_enable_bonding_failure(self):
        utils.system.expect_call('service network glag-enable',
                                 ignore_status=True)
        self.netif_setup()
        self.wait_for_carrier(num_trys=120)

        # run and check
        failed = True
        try:
            net_utils.enable_bonding()
        except error.TestError:
            failed = False

        self.assertFalse(failed)
        self.god.check_playback()


    def test_disable_bonding(self):
        utils.system.expect_call('service network glag-disable',
                                 ignore_status=True)
        self.netif_setup()
        self.wait_for_carrier()

        # run and test
        net_utils.disable_bonding()
        self.god.check_playback()


    def create_netif(self):
        self.netif_setup()
        self.netif = net_utils.netif('eth0')
        self.god.check_playback()


    def test_netif_restore(self):
        self.create_netif()

        # stub some stuff
        self.god.stub_function(self.netif, "disable_loopback")
        self.god.stub_function(self.netif, "set_ipaddr")
        self.god.stub_function(self.netif, "down")

        self.netif.was_loopback_enabled = False
        self.netif.was_down = True

        # record
        self.netif.disable_loopback.expect_call()
        self.netif.set_ipaddr.expect_call('127.0.0.1')
        self.netif.down.expect_call()

        # run
        self.netif.restore()
        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
