#!/usr/bin/python
import unittest, os, socket, time, sys, struct
import common
import utils
from autotest_lib.client.bin.net import net_utils, net_utils_mock
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import error


class TestNetUtils(unittest.TestCase):
    class network_interface_mock(net_utils_mock.network_interface_mock):
        def __init__(self, iface='some_name', test_init=False):
            super(TestNetUtils.network_interface_mock,
                  self).__init__(iface=iface, test_init=test_init)


    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "system")
        self.god.stub_function(utils, "system_output")
        self.god.stub_function(utils, "module_is_loaded")
        self.god.stub_function(net_utils, "open")
        self.god.stub_function(time, 'sleep')

        self.god.stub_with(net_utils,"bond", net_utils.bonding)
        self.god.stub_with(os, 'open', net_utils_mock.os_open)
        self.god.stub_with(net_utils, 'netif', net_utils_mock.netutils_netif)

        os.environ['AUTODIR'] = "autodir"


    def tearDown(self):
        self.god.unstub_all()
        del os.environ['AUTODIR']


    #
    # test network_util
    #
    def test_network_util_reset(self):
        utils.system.expect_call('service network restart', ignore_status=False)
        net_utils.network_utils().reset()
        self.god.check_playback()


    def test_network_util_start(self):
        utils.system.expect_call('service network start', ignore_status=False)

        net_utils.network_utils().start()
        self.god.check_playback()


    def test_network_util_stop(self):
        utils.system.expect_call('service network stop', ignore_status=False)

        net_utils.network_utils().stop()
        self.god.check_playback()


    def test_network_util_disable_ip_local_loopback(self):
        msg = "echo '1' > /proc/sys/net/ipv4/route/no_local_loopback"
        utils.system.expect_call(msg, ignore_status=False)
        msg = 'echo 1 > /proc/sys/net/ipv4/route/flush'
        utils.system.expect_call(msg, ignore_status=False)

        net_utils.network_utils().disable_ip_local_loopback()
        self.god.check_playback()


    def test_network_util_enable_ip_local_loopback(self):
        msg = "echo '0' > /proc/sys/net/ipv4/route/no_local_loopback"
        utils.system.expect_call(msg, ignore_status=False)
        msg = 'echo 1 > /proc/sys/net/ipv4/route/flush'
        utils.system.expect_call(msg, ignore_status=False)

        net_utils.network_utils().enable_ip_local_loopback()
        self.god.check_playback()


    #
    # test network_interface
    #
    def test_network_interface_init(self):
        self.god.stub_function(socket, 'socket')
        s = net_utils_mock.socket_stub('eth0', socket, socket)
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW).and_return(s)
        self.god.stub_function(s, 'bind')
        self.god.stub_function(s, 'settimeout')
        s.settimeout.expect_call(net_utils.TIMEOUT)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        mock_netif = self.network_interface_mock(iface='eth0', test_init=True)
        self.god.check_playback()
        self.assertEquals(mock_netif.ethtool, 'ethtool')
        self.assertEquals(mock_netif._name, 'eth0')
        self.assertEquals(mock_netif.was_down, 'is_down')
        self.assertEquals(mock_netif.orig_ipaddr, 'get_ipaddr')
        self.assertEquals(mock_netif.was_loopback_enabled,
                          'is_loopback_enabled')
        self.assertEquals(mock_netif._socket, s)


    def test_network_interface_restore(self):
        mock_netif = self.network_interface_mock('eth0')

        mock_netif.was_loopback_enabled = False
        mock_netif.loopback_enabled = True
        mock_netif.was_down = False

        self.god.stub_function(net_utils.bonding, 'is_enabled')

        # restore using phyint
        cmd = 'ifconfig %s %s' % (mock_netif._name, mock_netif.orig_ipaddr)
        utils.system.expect_call(cmd)

        net_utils.bonding.is_enabled.expect_call().and_return(False)

        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        mock_netif.restore()
        self.god.check_playback()


        # restore using mac
        cmd = 'ifconfig %s %s' % (mock_netif._name, mock_netif.orig_ipaddr)
        utils.system.expect_call(cmd)

        net_utils.bonding.is_enabled.expect_call().and_return(False)

        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)

        cmd = '%s -L %s %s %s' % (mock_netif.ethtool,
                                  mock_netif._name, 'mac', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        mock_netif.restore()
        self.god.check_playback()

        # check that down is restored
        mock_netif.was_loopback_enabled = False
        mock_netif.loopback_enabled = True
        mock_netif.was_down = True

        cmd = 'ifconfig %s %s' % (mock_netif._name, mock_netif.orig_ipaddr)
        utils.system.expect_call(cmd)

        net_utils.bonding.is_enabled.expect_call().and_return(False)

        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)

        cmd = 'ifconfig %s down' % mock_netif._name
        utils.system.expect_call(cmd)

        mock_netif.restore()
        self.god.check_playback()

        # check that loopback, down are done in sequence
        mock_netif.was_loopback_enabled = True
        mock_netif.loopback_enabled = True
        mock_netif.was_down = True

        cmd = 'ifconfig %s %s' % (mock_netif._name,
                                  mock_netif.orig_ipaddr)

        utils.system.expect_call(cmd)
        cmd = 'ifconfig %s down' % mock_netif._name
        utils.system.expect_call(cmd)

        mock_netif.restore()
        self.god.check_playback()

        # prior loopback matches current loopback
        mock_netif.was_loopback_enabled = False
        mock_netif.loopback_enabled = False
        mock_netif.was_down = True

        cmd = 'ifconfig %s %s' % (mock_netif._name,
                                  mock_netif.orig_ipaddr)
        utils.system.expect_call(cmd)
        cmd = 'ifconfig %s down' % mock_netif._name
        utils.system.expect_call(cmd)

        mock_netif.restore()
        self.god.check_playback()


    def test_network_interface_get_name(self):
        mock_netif = self.network_interface_mock(iface='eth0')
        self.assertEquals(mock_netif.get_name(), 'eth0')


    def test_network_interface_parse_ethtool(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return('\n field: match')
        self.assertEquals(mock_netif.parse_ethtool('field', 'some|match'),
                          'match')

        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(None)
        self.assertEquals(mock_netif.parse_ethtool('field',
                                                   'some|match'), '')

        utils.system_output.expect_call(cmd).and_return(' field: match')
        self.assertEquals(mock_netif.parse_ethtool('field',
                                                   'some|match'), '')
        self.god.check_playback()


    def test_network_interface_get_stats(self):
        mock_netif = self.network_interface_mock()
        self.god.stub_function(os, 'listdir')
        stat_path = '/sys/class/net/%s/statistics/' % mock_netif._name

        # no stat found
        os.listdir.expect_call(stat_path).and_return(())
        self.assertEquals(mock_netif.get_stats(), {})
        self.god.check_playback()

        # can not open stat file
        os.listdir.expect_call(stat_path).and_return(('some_stat',))
        f = self.god.create_mock_class(file, 'file')
        net_utils.open.expect_call(stat_path + 'some_stat', 'r').and_return(None)
        self.assertEquals(mock_netif.get_stats(), {})
        self.god.check_playback()

        # found a single stat
        os.listdir.expect_call(stat_path).and_return(('some_stat',))
        f = self.god.create_mock_class(file, 'file')
        net_utils.open.expect_call(stat_path + 'some_stat', 'r').and_return(f)
        f.read.expect_call().and_return(1234)
        f.close.expect_call()
        self.assertEquals(mock_netif.get_stats(), {'some_stat':1234})
        self.god.check_playback()

        # found multiple stats
        os.listdir.expect_call(stat_path).and_return(('stat1','stat2'))
        f = self.god.create_mock_class(file, 'file')
        net_utils.open.expect_call(stat_path + 'stat1', 'r').and_return(f)
        f.read.expect_call().and_return(1234)
        f.close.expect_call()
        net_utils.open.expect_call(stat_path + 'stat2', 'r').and_return(f)
        f.read.expect_call().and_return(5678)
        f.close.expect_call()

        self.assertEquals(mock_netif.get_stats(), {'stat1':1234, 'stat2':5678})
        self.god.check_playback()


    def test_network_interface_get_stats_diff(self):
        mock_netif = self.network_interface_mock()
        self.god.stub_function(os, 'listdir')
        stat_path = '/sys/class/net/%s/statistics/' % mock_netif._name

        os.listdir.expect_call(stat_path).and_return(('stat1','stat2', 'stat4'))
        f = self.god.create_mock_class(file, 'file')
        net_utils.open.expect_call(stat_path + 'stat1', 'r').and_return(f)
        f.read.expect_call().and_return(1234)
        f.close.expect_call()
        net_utils.open.expect_call(stat_path + 'stat2', 'r').and_return(f)
        f.read.expect_call().and_return(0)
        f.close.expect_call()
        net_utils.open.expect_call(stat_path + 'stat4', 'r').and_return(f)
        f.read.expect_call().and_return(10)
        f.close.expect_call()
        self.assertEquals(mock_netif.get_stats_diff({'stat1':1, 'stat2':2,
                                                     'stat3':0}),
                          {'stat1':1233, 'stat2':-2, 'stat4':10})
        self.god.check_playback()


    def test_network_interface_get_driver(self):
        mock_netif = self.network_interface_mock()
        mock_netif.get_driver = net_utils.network_interface.get_driver
        self.god.stub_function(os, 'readlink')
        stat_path = '/sys/class/net/%s/device/driver' % mock_netif._name
        os.readlink.expect_call(stat_path).and_return((
                                                  stat_path+'/driver_name'))
        self.assertEquals(mock_netif.get_driver(mock_netif), 'driver_name')
        self.god.check_playback()


    def test_network_interface_get_carrier(self):
        mock_netif = self.network_interface_mock()
        self.god.stub_function(os, 'readlink')
        stat_path = '/sys/class/net/%s/carrier' % mock_netif._name
        f = self.god.create_mock_class(file, 'file')
        net_utils.open.expect_call(stat_path).and_return(f)
        f.read.expect_call().and_return(' 1 ')
        f.close.expect_call()
        self.assertEquals(mock_netif.get_carrier(), '1')
        self.god.check_playback()

        net_utils.open.expect_call(stat_path).and_return(f)
        f.read.expect_call().and_return(' 0 ')
        f.close.expect_call()
        self.assertEquals(mock_netif.get_carrier(), '0')
        self.god.check_playback()

        net_utils.open.expect_call(stat_path).and_return(f)
        f.read.expect_call().and_return('')
        f.close.expect_call()
        self.assertEquals(mock_netif.get_carrier(), '')
        self.god.check_playback()

        net_utils.open.expect_call(stat_path).and_return(None)
        self.assertEquals(mock_netif.get_carrier(), '')
        self.god.check_playback()


    def test_network_interface_is_autoneg_advertised(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n Advertised auto-negotiation: Yes')
        self.assertEquals(mock_netif.is_autoneg_advertised(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n Advertised auto-negotiation: No')
        self.assertEquals(mock_netif.is_autoneg_advertised(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_autoneg_advertised(), False)
        self.god.check_playback()


    def test_network_interface_get_speed(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n Speed: 1000')
        self.assertEquals(mock_netif.get_speed(), 1000)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n Speed: 10000')
        self.assertEquals(mock_netif.get_speed(), 10000)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')

        try:
            mock_netif.get_speed()
        except ValueError:
            pass
        else:
            self.assertEquals(0,1)
        self.god.check_playback()


    def test_network_interface_is_full_duplex(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n Duplex: Full')
        self.assertEquals(mock_netif.is_full_duplex(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n Duplex: Half')
        self.assertEquals(mock_netif.is_full_duplex(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_full_duplex(), False)
        self.god.check_playback()


    def test_network_interface_is_autoneg_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n Auto-negotiation: on')
        self.assertEquals(mock_netif.is_autoneg_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n Auto-negotiation: off')
        self.assertEquals(mock_netif.is_autoneg_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_autoneg_on(), False)
        self.god.check_playback()


    def test_network_interface_get_wakeon(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n Wake-on: g')
        self.assertEquals(mock_netif.get_wakeon(), 'g')
        self.god.check_playback()


    def test_network_interface_is_rx_summing_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-k', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n rx-checksumming: on')
        self.assertEquals(mock_netif.is_rx_summing_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n rx-checksumming: off')
        self.assertEquals(mock_netif.is_rx_summing_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_rx_summing_on(), False)
        self.god.check_playback()


    def test_network_interface_is_tx_summing_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-k', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n tx-checksumming: on')
        self.assertEquals(mock_netif.is_tx_summing_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n tx-checksumming: off')
        self.assertEquals(mock_netif.is_tx_summing_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_tx_summing_on(), False)
        self.god.check_playback()


    def test_network_interface_is_scatter_gather_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-k', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n scatter-gather: on')
        self.assertEquals(mock_netif.is_scatter_gather_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n scatter-gather: off')
        self.assertEquals(mock_netif.is_scatter_gather_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_scatter_gather_on(), False)
        self.god.check_playback()


    def test_network_interface_is_tso_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-k', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n tcp segmentation offload: on')
        self.assertEquals(mock_netif.is_tso_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n tcp segmentation offload: off')
        self.assertEquals(mock_netif.is_tso_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_tso_on(), False)
        self.god.check_playback()


    def test_network_interface_is_pause_autoneg_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-a', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n Autonegotiate: on')
        self.assertEquals(mock_netif.is_pause_autoneg_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n Autonegotiate: off')
        self.assertEquals(mock_netif.is_pause_autoneg_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_pause_autoneg_on(), False)
        self.god.check_playback()


    def test_network_interface_is_tx_pause_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-a', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n TX: on')
        self.assertEquals(mock_netif.is_tx_pause_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n TX: off')
        self.assertEquals(mock_netif.is_tx_pause_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_tx_pause_on(), False)
        self.god.check_playback()


    def test_network_interface_is_rx_pause_on(self):
        mock_netif = self.network_interface_mock()
        cmd = '%s %s %s' % (mock_netif.ethtool, '-a', mock_netif._name)

        utils.system_output.expect_call(cmd).and_return(
            '\n RX: on')
        self.assertEquals(mock_netif.is_rx_pause_on(), True)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return(
            '\n RX: off')
        self.assertEquals(mock_netif.is_rx_pause_on(), False)
        self.god.check_playback()

        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_rx_pause_on(), False)
        self.god.check_playback()


    def test_network_interface_enable_loopback(self):
        mock_netif = self.network_interface_mock('eth0')

        mock_netif.was_loopback_enabled = False
        mock_netif.loopback_enabled = False
        mock_netif.was_down = False

        self.god.stub_function(net_utils.bonding, 'is_enabled')

        # restore using phyint
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        mock_netif.enable_loopback()
        self.god.check_playback()

        # restore using mac
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'mac', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        mock_netif.enable_loopback()
        self.god.check_playback()

        # catch exception on phyint and mac failures
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'mac', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)
        try:
            mock_netif.enable_loopback()
        except error.TestError:
            pass
        else:
            self.assertEquals(0,1)
        self.god.check_playback()

        # catch exception on bond enabled
        net_utils.bonding.is_enabled.expect_call().and_return(True)
        try:
            mock_netif.enable_loopback()
        except error.TestError:
            pass
        else:
            self.assertEquals(0,1)
        self.god.check_playback()

        # check that setting tg3 and bnx2x driver have a sleep call
        mock_netif.driver = 'tg3'
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        time.sleep.expect_call(1)
        mock_netif.enable_loopback()
        self.god.check_playback()

        mock_netif.driver = 'bnx2x'
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'enable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        time.sleep.expect_call(1)
        mock_netif.enable_loopback()
        self.god.check_playback()


    def test_network_interface_disable_loopback(self):
        mock_netif = self.network_interface_mock('eth0')

        mock_netif.was_loopback_enabled = False
        mock_netif.loopback_enabled = True
        mock_netif.was_down = False

        self.god.stub_function(net_utils.bonding, 'is_enabled')

        # restore using phyint
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        mock_netif.disable_loopback()
        self.god.check_playback()

        # restore using mac
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'mac', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(0)
        mock_netif.disable_loopback()
        self.god.check_playback()

        # catch exception on bonding enabled
        net_utils.bonding.is_enabled.expect_call().and_return(True)
        try:
            mock_netif.disable_loopback()
        except error.TestError:
            pass
        else:
            self.assertEquals(0,1)
        self.god.check_playback()

        # catch exception on phyint and mac failures
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'phyint', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)
        cmd = '%s -L %s %s %s' % (mock_netif.ethtool, mock_netif._name,
                                  'mac', 'disable')
        utils.system.expect_call(cmd, ignore_status=True).and_return(1)
        try:
            mock_netif.disable_loopback()
        except error.TestError:
            pass
        else:
            self.assertEquals(0,1)
        self.god.check_playback()


    def test_network_interface_is_loopback_enabled(self):
        mock_netif = self.network_interface_mock('eth0')
        mock_netif.is_loopback_enabled = \
            net_utils.network_interface.is_loopback_enabled
        try:
            mock_netif.is_loopback_enabled(mock_netif)
        except error.TestError:
            pass
        else:
            self.assertEquals(0,1)
        self.god.check_playback()

        self.god.stub_function(net_utils.bonding, 'is_enabled')
        mock_netif._name = 'eth0'
        net_utils.bonding.is_enabled.expect_call().and_return(False)
        cmd = '%s -l %s' % (mock_netif.ethtool, mock_netif._name)
        utils.system_output.expect_call(cmd).and_return('')
        self.assertEquals(mock_netif.is_loopback_enabled(mock_netif), False)
        self.god.check_playback()

        for ifname in ('eth0', 'eth1', 'eth2', 'eth3', 'eth4'):
            mock_netif._name = ifname
            for bond_enable in (True, False):
                for state in (('disabled', 'disabled', 'enabled'),
                              ('disabled', 'enabled', 'disabled'),
                              ('enabled', 'disabled', 'disabled'),
                              ('disabled', 'disabled', 'disabled')):
                    net_utils.bonding.is_enabled.expect_call().and_return(
                        bond_enable)
                    if bond_enable:
                        self.assertEquals(mock_netif.is_loopback_enabled(
                            mock_netif), False)
                    else:
                        cmd = '%s -l %s' % (mock_netif.ethtool, mock_netif._name)
                        out = 'MAC loopback is %s\n'\
                              'PHY internal loopback is %s\n'\
                              'PHY external loopback is %s' % (
                            state[0], state[1], state[2])
                        utils.system_output.expect_call(cmd).and_return(out)
                        self.assertEquals(mock_netif.is_loopback_enabled(
                            mock_netif), 'enabled' in state)
                    self.god.check_playback()


    def test_network_interface_enable_promisc(self):
        mock_netif = self.network_interface_mock('eth0')
        cmd = 'ifconfig %s promisc' % mock_netif._name
        utils.system.expect_call(cmd)
        mock_netif.enable_promisc()
        self.god.check_playback()


    def test_network_interface_disable_promisc(self):
        mock_netif = self.network_interface_mock()
        cmd = 'ifconfig %s -promisc' % mock_netif._name
        utils.system.expect_call(cmd)
        mock_netif.disable_promisc()
        self.god.check_playback()


    def test_network_interface_get_hwaddr(self):
        mock_netif = self.network_interface_mock()
        f = self.god.create_mock_class(file, 'file')
        net_utils.open.expect_call('/sys/class/net/%s/address'
                                       % mock_netif._name).and_return(f)
        hw_addr = '00:0e:0c:c3:7d:a8'
        f.read.expect_call().and_return(' ' + hw_addr + ' ')
        f.close.expect_call()
        self.assertEquals(mock_netif.get_hwaddr(), hw_addr)
        self.god.check_playback()


    def test_network_interface_set_hwaddr(self):
        mock_netif = self.network_interface_mock()
        hw_addr = '00:0e:0c:c3:7d:a8'
        cmd = 'ifconfig %s hw ether %s' % (mock_netif._name,
                                           hw_addr)
        utils.system.expect_call(cmd)
        mock_netif.set_hwaddr(hw_addr)
        self.god.check_playback()


    def test_network_interface_add_maddr(self):
        mock_netif = self.network_interface_mock()
        maddr = '01:00:5e:00:00:01'
        cmd = 'ip maddr add %s dev %s' % (maddr, mock_netif._name)
        utils.system.expect_call(cmd)
        mock_netif.add_maddr(maddr)
        self.god.check_playback()


    def test_network_interface_del_maddr(self):
        mock_netif = self.network_interface_mock()
        maddr = '01:00:5e:00:00:01'
        cmd = 'ip maddr del %s dev %s' % (maddr, mock_netif._name)
        utils.system.expect_call(cmd)
        mock_netif.del_maddr(maddr)
        self.god.check_playback()


    def test_network_interface_get_ipaddr(self):
        mock_netif = self.network_interface_mock()
        ip_addr = '110.211.112.213'
        out_format = \
          'eth0      Link encap:Ethernet  HWaddr 00:0E:0C:C3:7D:A8\n'\
          '          inet addr:%s  Bcast:10.246.90.255'\
          ' Mask:255.255.255.0\n'\
          '          UP BROADCAST RUNNING MASTER MULTICAST  MTU:1500'\
          ' Metric:1\n'\
          '          RX packets:463070 errors:0 dropped:0 overruns:0'\
          ' frame:0\n'\
          '          TX packets:32548 errors:0 dropped:0 overruns:0'\
          ' carrier:0\n'\
          '          collisions:0 txqueuelen:0'
        out = out_format % ip_addr

        cmd = 'ifconfig %s' % mock_netif._name
        utils.system_output.expect_call(cmd).and_return(out)
        self.assertEquals(mock_netif.get_ipaddr(), ip_addr)
        self.god.check_playback()

        cmd = 'ifconfig %s' % mock_netif._name
        utils.system_output.expect_call(cmd).and_return('some output')
        self.assertEquals(mock_netif.get_ipaddr(), '0.0.0.0')
        self.god.check_playback()

        cmd = 'ifconfig %s' % mock_netif._name
        utils.system_output.expect_call(cmd).and_return(None)
        self.assertEquals(mock_netif.get_ipaddr(), '0.0.0.0')
        self.god.check_playback()

        ip_addr = '1.2.3.4'
        out = out_format % ip_addr
        cmd = 'ifconfig %s' % mock_netif._name
        utils.system_output.expect_call(cmd).and_return(out)
        self.assertEquals(mock_netif.get_ipaddr(), ip_addr)
        self.god.check_playback()


    def test_network_interface_set_ipaddr(self):
        mock_netif = self.network_interface_mock()
        ip_addr = '1.2.3.4'
        cmd = 'ifconfig %s %s' % (mock_netif._name, ip_addr)
        utils.system.expect_call(cmd)
        mock_netif.set_ipaddr(ip_addr)
        self.god.check_playback()


    def test_network_interface_is_down(self):
        mock_netif = self.network_interface_mock()
        out_format = \
          'eth0      Link encap:Ethernet  HWaddr 00:0E:0C:C3:7D:A8\n'\
          '          inet addr:1.2.3.4  Bcast:10.246.90.255'\
          ' Mask:255.255.255.0\n'\
          '          %s BROADCAST RUNNING MASTER MULTICAST  MTU:1500'\
          ' Metric:1\n'\
          '          RX packets:463070 errors:0 dropped:0 overruns:0'\
          ' frame:0\n'\
          '          TX packets:32548 errors:0 dropped:0 overruns:0'\
          ' carrier:0\n'\
          '          collisions:0 txqueuelen:0'
        for state in ('UP', 'DOWN', 'NONE', ''):
            out = out_format % state
            cmd = 'ifconfig %s' % mock_netif._name
            utils.system_output.expect_call(cmd).and_return(out)
            self.assertEquals(mock_netif.is_down(), state != 'UP')
            self.god.check_playback()

        cmd = 'ifconfig %s' % mock_netif._name
        utils.system_output.expect_call(cmd).and_return(None)
        self.assertEquals(mock_netif.is_down(), False)
        self.god.check_playback()


    def test_network_interface_up(self):
        mock_netif = self.network_interface_mock()
        cmd = 'ifconfig %s up' % mock_netif._name
        utils.system.expect_call(cmd)
        mock_netif.up()
        self.god.check_playback()


    def test_network_interface_down(self):
        mock_netif = self.network_interface_mock()
        cmd = 'ifconfig %s down' % mock_netif._name
        utils.system.expect_call(cmd)
        mock_netif.down()
        self.god.check_playback()


    def test_network_interface_wait_for_carrier(self):
        mock_netif = self.network_interface_mock()
        mock_netif.wait_for_carrier = \
                             net_utils.network_interface.wait_for_carrier
        f = self.god.create_mock_class(file, 'file')
        spath = '/sys/class/net/%s/carrier' % mock_netif._name
        # y = 0 - test that an exception is thrown
        # y = 1, 100 - check that carrier is checked until timeout
        for y in (0, 1, 100):
            max_timeout = y
            if y:
                for x in xrange(max_timeout - 1):
                    net_utils.open.expect_call(spath).and_return(f)
                    f.read.expect_call().and_return(' ' + '0' + ' ')
                    f.close.expect_call()
                    time.sleep.expect_call(1)

                net_utils.open.expect_call(spath).and_return(f)
                f.read.expect_call().and_return(' ' + '1' + ' ')
                f.close.expect_call()
            try:
                mock_netif.wait_for_carrier(mock_netif, max_timeout)
            except:
                pass
            else:
                if not y:
                    self.assertEquals(0, 1)
            self.god.check_playback()


    def test_network_interface_send(self):
        mock_netif = self.network_interface_mock()
        mock_netif.send('test buffer')
        self.assertEquals(mock_netif._socket.send_val, 'test buffer')


    def test_network_interface_recv(self):
        mock_netif = self.network_interface_mock()
        test_str = 'test string'
        mock_netif._socket.recv_val = test_str
        rcv_str = mock_netif.recv(len(test_str))
        self.assertEquals(rcv_str, test_str)


    def test_network_interface_flush(self):
        mock_netif = self.network_interface_mock()
        self.god.stub_function(mock_netif._socket, 'close')
        mock_netif._socket.close.expect_call()
        s = self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW).and_return(s)
        s.settimeout.expect_call(net_utils.TIMEOUT)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))


    #
    # bonding tests
    #
    def test_bonding_is_enabled(self):
        try:
            net_utils.bond().is_enabled()
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)


    def test_bonding_is_bondable(self):
        try:
            net_utils.bond().is_enabled()
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)


    def test_bonding_enable(self):
        try:
            net_utils.bond().is_enabled()
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)


    def test_bonding_disable(self):
        try:
            net_utils.bond().is_enabled()
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)


    def test_bonding_get_mii_status(self):
        self.assertEquals(net_utils.bond().get_mii_status(), {})


    def test_get_mode_bonding(self):
        self.assertEquals(net_utils.bond().get_mode(), net_utils.bonding.NO_MODE)


    def test_bonding_wait_for_state_change(self):
        self.god.stub_function(utils, "ping_default_gateway")

        time.sleep.expect_call(10)
        utils.ping_default_gateway.expect_call().and_return(False)
        self.assertEquals(net_utils.bond().wait_for_state_change(), True)

        for x in xrange(9):
            time.sleep.expect_call(10)
            utils.ping_default_gateway.expect_call().and_return(True)

        time.sleep.expect_call(10)
        utils.ping_default_gateway.expect_call().and_return(False)
        self.assertEquals(net_utils.bond().wait_for_state_change(), True)

        for x in xrange(10):
            time.sleep.expect_call(10)
            utils.ping_default_gateway.expect_call().and_return(True)

        self.assertEquals(net_utils.bond().wait_for_state_change(), False)

        self.god.check_playback()


    def test_bonding_get_active_interfaces(self):
        self.assertEquals(net_utils.bond().get_active_interfaces(), [])
        self.god.check_playback()


    def test_bonding_get_slave_interfaces(self):
        self.assertEquals(net_utils.bond().get_slave_interfaces(), [])
        self.god.check_playback()


    #
    # ethernet tests
    #

    def test_ethernet_mac_string_to_binary(self):
        mac_bin = net_utils.ethernet.mac_string_to_binary('00:01:02:03:04:05')
        self.assertEqual(mac_bin, '\x00\x01\x02\x03\x04\x05')


    def test_ethernet_mac_binary_to_string(self):
        mac_str = net_utils.ethernet.mac_binary_to_string(
            '\x00\x01\x02\x03\x04\x05')
        self.assertEqual(mac_str, '00:01:02:03:04:05')


    def test_ethernet_pack(self):
        dst = net_utils.ethernet.mac_string_to_binary('00:01:02:03:04:05')
        src = net_utils.ethernet.mac_string_to_binary('16:17:18:19:1A:1B')
        protocol = 2030
        payload = 'some payload'
        frame = struct.pack("!6s6sH", dst, src, protocol) + payload
        self.assertEquals(net_utils.ethernet.pack(dst, src,protocol, payload),
                          frame)


    def test_ethernet_unpack(self):
        dst = net_utils.ethernet.mac_string_to_binary('00:01:02:03:04:05')
        src = net_utils.ethernet.mac_string_to_binary('16:17:18:19:1A:1B')
        protocol = 2030
        payload = 'some payload'
        frame = net_utils.ethernet.pack(dst, src, protocol, payload)
        uframe = net_utils.ethernet.unpack(frame)
        self.assertEquals(uframe[net_utils.ethernet.FRAME_KEY_DST_MAC], dst)
        self.assertEquals(uframe[net_utils.ethernet.FRAME_KEY_SRC_MAC], src)
        self.assertEquals(uframe[net_utils.ethernet.FRAME_KEY_PROTO], protocol)
        self.assertEquals(uframe[net_utils.ethernet.FRAME_KEY_PAYLOAD], payload)


    # raw_socket tests
    #
    def test_raw_socket_open(self):
        self.god.stub_function(socket, 'setdefaulttimeout')

        s = self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')

        # open without a protocol
        socket.setdefaulttimeout.expect_call(1)
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW).and_return(s)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        sock.open(protocol=None)

        self.god.check_playback()

        # double open should throw an exception
        try:
            sock.open()
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)

        self.god.check_playback()

        # open a protocol
        socket.setdefaulttimeout.expect_call(1)
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW,
                                  socket.htons(1234)).and_return(s)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        sock.open(protocol=1234)

        self.god.check_playback()


    def test_raw_socket_close(self):
        self.god.stub_function(socket, 'setdefaulttimeout')

        s = self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')

        # close without open
        socket.setdefaulttimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        try:
            sock.close()
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)

        # close after open
        socket.setdefaulttimeout.expect_call(1)
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW).and_return(s)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        sock.open(protocol=None)

        s.close.expect_call()
        sock.close()
        self.god.check_playback()


    def test_raw_socket_recv(self):
        self.god.stub_function(socket, 'setdefaulttimeout')

        self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')

        # rcv without open
        socket.setdefaulttimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        try:
            sock.recv(10)
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)

        self.god.check_playback()

        # open a protocol and try to get packets of varying sizes
        # I could not get socket.recv to get a mock expect_call. To keep
        # on going, added a socket stub
        s = net_utils_mock.socket_stub('eth0', socket, socket)
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW,
                                  socket.htons(1234)).and_return(s)

        self.god.stub_function(s, 'bind')
        self.god.stub_function(s, 'settimeout')
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        sock.open(protocol=1234)

        s.recv_val = ''
        self.assertEquals(sock.recv(1), (None, 0))

        s.recv_val = '\xFF' * (net_utils.ethernet.ETH_PACKET_MIN_SIZE-5)
        self.assertEquals(sock.recv(1), (None, 0))

        # when receiving a packet, make sure the timeout is not change
        s.recv_val = '\xEE' * (net_utils.ethernet.ETH_PACKET_MIN_SIZE-4)
        self.assertEquals(sock.recv(1), (s.recv_val, 1))

        s.recv_val = '\xDD' * (net_utils.ethernet.ETH_PACKET_MIN_SIZE)
        self.assertEquals(sock.recv(1), (s.recv_val, 1))

        s.recv_val = '\xCC' * (net_utils.ethernet.ETH_PACKET_MAX_SIZE)
        self.assertEquals(sock.recv(1), (s.recv_val, 1))

        s.recv_val = '\xBB' * (net_utils.ethernet.ETH_PACKET_MAX_SIZE+1)
        packet, time_left = sock.recv(1)
        self.assertEquals(len(packet), net_utils.ethernet.ETH_PACKET_MAX_SIZE)
        self.assertEquals(packet,
                          s.recv_val[:net_utils.ethernet.ETH_PACKET_MAX_SIZE])


        # test timeout
        s.recv_val = ''
        s.throw_timeout = False
        sock.recv(5)
        self.assertEquals(sock.recv(1), (None, 0))
        s.throw_timeout = True
        sock.recv(5)
        self.assertEquals(sock.recv(1), (None, 0))

        self.god.check_playback()


    def test_raw_socket_send(self):
        self.god.stub_function(socket, 'setdefaulttimeout')
        self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')
        self.god.stub_function(socket, 'send')

        # send without open
        socket.setdefaulttimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        try:
            sock.send('test this packet')
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)
        self.god.check_playback()

        # open a protocol and try to send a packet
        s = net_utils_mock.socket_stub('eth0', socket, socket)
        self.god.stub_function(s, 'bind')
        self.god.stub_function(s, 'settimeout')
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW,
                                  socket.htons(1234)).and_return(s)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        packet = '\xFF\xAA\xBB\xCC\xDD\x11packet data\x00\x00'
        s.send.expect_call(packet)
        sock.open(protocol=1234)
        sock.send(packet)
        self.god.check_playback()


    def test_raw_socket_send_to(self):
        self.god.stub_function(socket, 'setdefaulttimeout')
        self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')
        self.god.stub_function(socket, 'send')

        # send without open
        socket.setdefaulttimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        try:
            sock.send_to('0', '1', 1, 'test this packet')
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)
        self.god.check_playback()

        # open a protocol and try to send a packet
        s = net_utils_mock.socket_stub('eth0', socket, socket)
        self.god.stub_function(s, 'bind')
        self.god.stub_function(s, 'settimeout')
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW,
                                  socket.htons(1234)).and_return(s)
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        packet = '\x00\x00packet data\x00\x00'
        s.send.expect_call(packet)
        sock.open(protocol=1234)
        try:
            sock.send_to(None, None, 1, packet)
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)
        self.god.check_playback()

        dst_mac = '\x00\x01\x02\x03\x04\x05'
        src_mac = '\xFF\xEE\xDD\xCC\xBB\xAA'
        protocol = 1234
        s.send.expect_call(dst_mac+src_mac+'%d'%protocol+packet)
        sock.send_to(dst_mac, src_mac, protocol, packet)
        self.god.check_playback()


    def test_raw_socket_recv_from(self):

        def __set_clock(sock):
            time.clock.expect_call().and_return(0.0)
            time.clock.expect_call().and_return(0.0)
            time.clock.expect_call().and_return(float(sock.socket_timeout()) + 0.5)

        self.god.stub_function(socket, 'setdefaulttimeout')

        self.god.create_mock_class(socket.socket, "socket")
        self.god.stub_function(socket, 'socket')

        # rcv without open
        socket.setdefaulttimeout.expect_call(1)
        sock = net_utils.raw_socket('eth0')
        try:
            sock.recv_from(None, None, None)
        except error.TestError:
            pass
        else:
            self.assertEquals(1, 0)

        self.god.check_playback()

        # open a protocol and try to get packets of varying sizes
        # I could not get socket.recv to get a mock expect_call. To keep
        # on going, added a socket stub
        s = net_utils_mock.socket_stub('eth0', socket, socket)
        socket.socket.expect_call(socket.PF_PACKET,
                                  socket.SOCK_RAW,
                                  socket.htons(1234)).and_return(s)

        self.god.stub_function(s, 'bind')
        self.god.stub_function(s, 'settimeout')
        s.bind.expect_call(('eth0', net_utils.raw_socket.ETH_P_ALL))
        s.settimeout.expect_call(1)
        sock.open(protocol=1234)

        s.recv_val = ''
        dst_mac = net_utils.ethernet.mac_string_to_binary('00:01:02:03:04:05')
        src_mac = net_utils.ethernet.mac_string_to_binary('16:17:18:19:1A:1B')
        t_mac = net_utils.ethernet.mac_string_to_binary('E6:E7:E8:E9:EA:EB')
        protocol = 2030
        t_protocol = 1234
        data = '\xEE' * (net_utils.ethernet.ETH_PACKET_MIN_SIZE)

        # no data to receive at socket
        self.assertEquals(sock.recv_from(None, None, None), None)
        self.assertEquals(sock.recv_from(dst_mac, None, None), None)
        self.assertEquals(sock.recv_from(None, src_mac, None), None)
        self.assertEquals(sock.recv_from(None, None, protocol), None)

        # receive packet < min size
        s.recv_val = (struct.pack("!6s6sH", dst_mac, src_mac, protocol) +
                      'packet_to_short')
        self.assertEquals(sock.recv_from(None, None, None), None)

        # receive packet, filtering on mac address and protocol
        s.recv_val = struct.pack("!6s6sH", dst_mac, t_mac, t_protocol) + data
        frame = net_utils.ethernet.unpack(s.recv_val)
        self.assertEquals(sock.recv_from(None, None, None), frame)
        self.assertEquals(sock.recv_from(dst_mac, None, None), frame)

        # use time clock to speed up the timeout in send_to()
        self.god.stub_function(time, 'clock')
        __set_clock(sock)
        self.assertEquals(sock.recv_from(dst_mac, src_mac, None), None)
        __set_clock(sock)
        self.assertEquals(sock.recv_from(dst_mac, None, protocol), None)
        __set_clock(sock)
        self.assertEquals(sock.recv_from(dst_mac, src_mac, protocol), None)
        self.god.unstub(time, 'clock')

        s.recv_val = struct.pack("!6s6sH", dst_mac, src_mac, protocol) + data
        frame = net_utils.ethernet.unpack(s.recv_val)
        self.assertEquals(sock.recv_from(dst_mac, None, None), frame)
        self.assertEquals(sock.recv_from(dst_mac, src_mac, None), frame)
        self.assertEquals(sock.recv_from(dst_mac, src_mac, protocol), frame)
        self.assertEquals(sock.recv_from(None, None, protocol), frame)
        self.assertEquals(sock.recv_from(None, src_mac, None), frame)
        self.god.stub_function(time, 'clock')
        __set_clock(sock)
        self.assertEquals(sock.recv_from(None, None, t_protocol), None)
        __set_clock(sock)
        self.assertEquals(sock.recv_from(None, t_mac, None), None)
        self.god.unstub(time, 'clock')


        self.god.check_playback()


if __name__ == "__main__":
    unittest.main()
