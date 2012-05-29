"""Set of Mocks and stubs for network utilities unit tests.

Implement a set of mocks and stubs use to implement unit tests
for the network libraries.
"""

import socket
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.bin.net import net_utils


def os_open(*args, **kwarg):
    return os_stub('open')


class os_stub(mock.mock_function):
    def __init__(self, symbol, **kwargs):
        mock.mock_function.__init__(self, symbol, *kwargs)

    readval = ""
    def open(self, *args, **kwargs):
        return self

    def read(self, *args, **kwargs):
        return os_stub.readval


def netutils_netif(iface):
    return netif_stub(iface, 'net_utils', net_utils.netif)


class netif_stub(mock.mock_class):
    def __init__(self, iface, cls, name, *args, **kwargs):
        mock.mock_class.__init__(self, cls, name, args, *kwargs)


    def wait_for_carrier(self, timeout):
        return


class socket_stub(mock.mock_class):
    """Class use to mock sockets."""
    def __init__(self, iface, cls, name, *args, **kwargs):
        mock.mock_class.__init__(self, cls, name, args, *kwargs)
        self.recv_val = ''
        self.throw_timeout = False
        self.send_val = None
        self.timeout = None
        self.family = None
        self.type = None


    def close(self):
        pass


    def socket(self, family, type):
        self.family = family
        self.type = type


    def settimeout(self, timeout):
        self.timeout = timeout
        return


    def send(self, buf):
        self.send_val = buf


    def recv(self, size):
        if self.throw_timeout:
            raise socket.timeout

        if len(self.recv_val) > size:
            return self.recv_val[:size]
        return self.recv_val


    def bind(self, arg):
        pass


class network_interface_mock(net_utils.network_interface):
    def __init__(self, iface='some_name', test_init=False):
        self._test_init = test_init # test network_interface __init__()
        if self._test_init:
            super(network_interface_mock, self).__init__(iface)
            return

        self.ethtool = '/mock/ethtool'
        self._name = iface
        self.was_down = False
        self.orig_ipaddr = '1.2.3.4'
        self.was_loopback_enabled = False
        self._socket = socket_stub(iface, socket, socket)

        self.loopback_enabled = False
        self.driver = 'mock_driver'


    def is_down(self):
        if self._test_init:
            return 'is_down'
        return super(network_interface_mock, self).is_down()


    def get_ipaddr(self):
        if self._test_init:
            return 'get_ipaddr'
        return super(network_interface_mock, self).get_ipaddr()


    def is_loopback_enabled(self):
        if self._test_init:
            return 'is_loopback_enabled'
        return self.loopback_enabled


    def get_driver(self):
        return self.driver


    def wait_for_carrier(self, timeout=1):
        return
