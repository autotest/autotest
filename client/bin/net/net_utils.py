"""Convenience functions for use by network tests or whomever.

This library is to release in the public repository.
"""

import commands, os, re, socket, sys, time, struct
from autotest_lib.client.common_lib import error
import utils

TIMEOUT = 10 # Used for socket timeout and barrier timeout


class network_utils(object):
    def reset(self, ignore_status=False):
        utils.system('service network restart', ignore_status=ignore_status)


    def start(self, ignore_status=False):
        utils.system('service network start', ignore_status=ignore_status)


    def stop(self, ignore_status=False):
        utils.system('service network stop', ignore_status=ignore_status)


    def disable_ip_local_loopback(self, ignore_status=False):
        utils.system("echo '1' > /proc/sys/net/ipv4/route/no_local_loopback",
                     ignore_status=ignore_status)
        utils.system('echo 1 > /proc/sys/net/ipv4/route/flush',
                     ignore_status=ignore_status)


    def enable_ip_local_loopback(self, ignore_status=False):
        utils.system("echo '0' > /proc/sys/net/ipv4/route/no_local_loopback",
                     ignore_status=ignore_status)
        utils.system('echo 1 > /proc/sys/net/ipv4/route/flush',
                     ignore_status=ignore_status)


    def process_mpstat(self, mpstat_out, sample_count, loud = True):
        """Parses mpstat output of the following two forms:
        02:10:17     0    0.00    0.00    0.00    0.00    0.00    0.00   \
        0.00  100.00   1012.87
        02:10:13 PM    0    0.00    0.00    0.00    0.00    0.00    0.00 \
        0.00  100.00   1019.00
        """
        mpstat_keys = ['time', 'CPU', 'user', 'nice', 'sys', 'iowait', 'irq',
                       'soft', 'steal', 'idle', 'intr/s']
        if loud:
            print mpstat_out

        # Remove the optional AM/PM appearing in time format
        mpstat_out = mpstat_out.replace('AM', '')
        mpstat_out = mpstat_out.replace('PM', '')

        regex = re.compile('(\S+)')
        stats = []
        for line in mpstat_out.splitlines()[3:]:
            match = regex.findall(line)
            # Skip the "Average" computed by mpstat. We are gonna compute the
            # average ourself.  Pick only the aggregate 'all' CPU results
            if match and match[0] != 'Average:' and match[1] == 'all':
                stats.append(dict(zip(mpstat_keys, match)))

        if sample_count >= 5:
            # Throw away first and last sample
            stats = stats[1:-1]

        cpu_stats = {}
        for key in ['user', 'nice', 'sys', 'iowait', 'irq', 'soft', 'steal',
                    'idle', 'intr/s']:
            x = [float(row[key]) for row in stats]
            if len(x):
                count = len(x)
            else:
                print 'net_utils.network_utils.process_mpstat: count is 0!!!\n'
                count = 1
            cpu_stats[key] = sum(x) / count

        return cpu_stats


def network():
    try:
        from autotest_lib.client.bin.net import site_net_utils
        return site_net_utils.network_utils()
    except:
        return network_utils()


class network_interface(object):

    ENABLE, DISABLE = (True, False)

    def __init__(self, name):
        autodir = os.environ['AUTODIR']
        self.ethtool = 'ethtool'
        self._name = name
        self.was_down = self.is_down()
        self.orig_ipaddr = self.get_ipaddr()
        self.was_loopback_enabled = self.is_loopback_enabled()
        self._socket = socket.socket(socket.PF_PACKET, socket.SOCK_RAW)
        self._socket.settimeout(TIMEOUT)
        self._socket.bind((name, raw_socket.ETH_P_ALL))


    def restore(self):
        self.set_ipaddr(self.orig_ipaddr)
        # TODO (msb): The additional conditional guard needs cleanup:
        #             Underlying driver should simply perform a noop
        #             for disabling loopback on an already-disabled device,
        #             instead of returning non-zero exit code.

        # To avoid sending a RST to the autoserv ssh connection
        # don't disable loopback until the IP address is restored.
        if not self.was_loopback_enabled and self.is_loopback_enabled():
            self.disable_loopback()
        if self.was_down:
            self.down()


    def get_name(self):
        return self._name


    def parse_ethtool(self, field, match, option='', next_field=''):
        output = utils.system_output('%s %s %s' % (self.ethtool,
                                                   option, self._name))
        if output:
            match = re.search('\n\s*%s:\s*(%s)%s' %
                              (field, match, next_field), output, re.S)
            if match:
                return match.group(1)

        return ''


    def get_stats(self):
        stats = {}
        stats_path = '/sys/class/net/%s/statistics/' % self._name
        for stat in os.listdir(stats_path):
            f = open(stats_path + stat, 'r')
            if f:
                stats[stat] = int(f.read())
                f.close()
        return stats


    def get_stats_diff(self, orig_stats):
        stats = self.get_stats()
        for stat in stats.keys():
            if stat in orig_stats:
                stats[stat] = stats[stat] - orig_stats[stat]
            else:
                stats[stat] = stats[stat]
        return stats


    def get_driver(self):
        driver_path = os.readlink('/sys/class/net/%s/device/driver' %
                                  self._name)
        return os.path.basename(driver_path)


    def get_carrier(self):
        f = open('/sys/class/net/%s/carrier' % self._name)
        if not f:
            return ''
        carrier = f.read().strip()
        f.close()
        return carrier


    def get_supported_link_modes(self):
        result = self.parse_ethtool('Supported link modes', '.*',
                                    next_field='Supports auto-negotiation')
        return result.split()


    def get_advertised_link_modes(self):
        result = self.parse_ethtool('Advertised link modes', '.*',
                                    next_field='Advertised auto-negotiation')
        return result.split()


    def is_autoneg_advertised(self):
        result = self.parse_ethtool('Advertised auto-negotiation',
                                        'Yes|No')
        return result == 'Yes'


    def get_speed(self):
        return int(self.parse_ethtool('Speed', '\d+'))


    def is_full_duplex(self):
        result = self.parse_ethtool('Duplex', 'Full|Half')
        return result == 'Full'


    def is_autoneg_on(self):
        result = self.parse_ethtool('Auto-negotiation', 'on|off')
        return result == 'on'


    def get_wakeon(self):
        return self.parse_ethtool('Wake-on', '\w+')


    def is_rx_summing_on(self):
        result = self.parse_ethtool('rx-checksumming', 'on|off', '-k')
        return result == 'on'


    def is_tx_summing_on(self):
        result = self.parse_ethtool('tx-checksumming', 'on|off', '-k')
        return result == 'on'


    def is_scatter_gather_on(self):
        result = self.parse_ethtool('scatter-gather', 'on|off', '-k')
        return result == 'on'


    def is_tso_on(self):
        result = self.parse_ethtool('tcp segmentation offload',
                                    'on|off', '-k')
        return result == 'on'


    def is_pause_autoneg_on(self):
        result = self.parse_ethtool('Autonegotiate', 'on|off', '-a')
        return result == 'on'


    def is_tx_pause_on(self):
        result = self.parse_ethtool('TX', 'on|off', '-a')
        return result == 'on'


    def is_rx_pause_on(self):
        result = self.parse_ethtool('RX', 'on|off', '-a')
        return result == 'on'


    def _set_loopback(self, mode, enable_disable):
        return utils.system('%s -L %s %s %s' %
                      (self.ethtool, self._name, mode, enable_disable),
                      ignore_status=True)


    def enable_loopback(self):
        # If bonded do not set loopback mode.
        # Try mac loopback first then phy loopback
        # If both fail, raise an error
        if (bond().is_enabled() or
            (self._set_loopback('phyint', 'enable') > 0 and
             self._set_loopback('mac', 'enable') > 0)):
            raise error.TestError('Unable to enable loopback')
        # Add a 1 second wait for drivers which do not have
        # a synchronous loopback enable
        # TODO (msb); Remove this wait once the drivers are fixed
        if self.get_driver() in ['tg3', 'bnx2x']:
            time.sleep(1)
        self.wait_for_carrier(timeout=30)


    def disable_loopback(self):
        # If bonded, to not disable loopback.
        # Try mac loopback first then phy loopback
        # If both fail, raise an error
        if (bond().is_enabled() or
            (self._set_loopback('phyint', 'disable') > 0 and
             self._set_loopback('mac', 'disable') > 0)):
            raise error.TestError('Unable to disable loopback')


    def is_loopback_enabled(self):
        # Don't try ethtool -l on a bonded host
        if bond().is_enabled():
            return False
        output = utils.system_output('%s -l %s' % (self.ethtool, self._name))
        if output:
            return 'enabled' in output
        return False


    def enable_promisc(self):
        utils.system('ifconfig %s promisc' % self._name)


    def disable_promisc(self):
        utils.system('ifconfig %s -promisc' % self._name)


    def get_hwaddr(self):
        f = open('/sys/class/net/%s/address' % self._name)
        hwaddr = f.read().strip()
        f.close()
        return hwaddr


    def set_hwaddr(self, hwaddr):
        utils.system('ifconfig %s hw ether %s' % (self._name, hwaddr))


    def add_maddr(self, maddr):
        utils.system('ip maddr add %s dev %s' % (maddr, self._name))


    def del_maddr(self, maddr):
        utils.system('ip maddr del %s dev %s' % (maddr, self._name))


    def get_ipaddr(self):
        ipaddr = "0.0.0.0"
        output = utils.system_output('ifconfig %s' % self._name)
        if output:
            match = re.search("inet addr:([\d\.]+)", output)
            if match:
                ipaddr = match.group(1)
        return ipaddr


    def set_ipaddr(self, ipaddr):
        utils.system('ifconfig %s %s' % (self._name, ipaddr))


    def is_down(self):
        output = utils.system_output('ifconfig %s' % self._name)
        if output:
            return 'UP' not in output
        return False

    def up(self):
        utils.system('ifconfig %s up' % self._name)


    def down(self):
        utils.system('ifconfig %s down' % self._name)


    def wait_for_carrier(self, timeout=60):
        while timeout and self.get_carrier() != '1':
            timeout -= 1
            time.sleep(1)
        if timeout == 0:
            raise error.TestError('Timed out waiting for carrier.')


    def send(self, buf):
        self._socket.send(buf)


    def recv(self, len):
        return self._socket.recv(len)


    def flush(self):
        self._socket.close()
        self._socket = socket.socket(socket.PF_PACKET, socket.SOCK_RAW)
        self._socket.settimeout(TIMEOUT)
        self._socket.bind((self._name, raw_socket.ETH_P_ALL))


def netif(name):
    try:
        from autotest_lib.client.bin.net import site_net_utils
        return site_net_utils.network_interface(name)
    except:
        return network_interface(name)


class bonding(object):
    """This class implements bonding interface abstraction."""

    NO_MODE = 0
    AB_MODE = 1
    AD_MODE = 2

    def is_enabled(self):
        raise error.TestError('Undefined')


    def is_bondable(self):
        raise error.TestError('Undefined')


    def enable(self):
        raise error.TestError('Undefined')


    def disable(self):
        raise error.TestError('Undefined')


    def get_mii_status(self):
        return {}


    def get_mode(self):
        return bonding.NO_MODE


    def wait_for_state_change(self):
        """Wait for bonding state change.

        Wait up to 90 seconds to successfully ping the gateway.
        This is to know when LACP state change has converged.
        (0 seconds is 3x lacp timeout, use by protocol)
        """

        netif('eth0').wait_for_carrier(timeout=60)
        wait_time = 0
        while wait_time < 100:
            time.sleep(10)
            if not utils.ping_default_gateway():
                return True
            wait_time += 10
        return False


    def get_active_interfaces(self):
        return []


    def get_slave_interfaces(self):
        return []


def bond():
    try:
        from autotest_lib.client.bin.net import site_net_utils
        return site_net_utils.bonding()
    except:
        return bonding()


class raw_socket(object):
    """This class implements an raw socket abstraction."""
    ETH_P_ALL = 0x0003 # Use for binding a RAW Socket to all protocols
    SOCKET_TIMEOUT = 1
    def __init__(self, iface_name):
        """Initialize an interface for use.

        Args:
          iface_name: 'eth0'  interface name ('eth0, eth1,...')
        """
        self._name = iface_name
        self._socket = None
        self._socket_timeout = raw_socket.SOCKET_TIMEOUT
        socket.setdefaulttimeout(self._socket_timeout)
        if self._name is None:
            raise error.TestError('Invalid interface name')


    def socket(self):
        return self._socket


    def socket_timeout(self):
        """Get the timeout use by recv_from"""
        return self._socket_timeout


    def set_socket_timeout(self, timeout):
        """Set the timeout use by recv_from.

        Args:
          timeout: time in seconds
        """
        self._socket_timeout = timeout

    def open(self, protocol=None):
        """Opens the raw socket to send and receive.

        Args:
          protocol : short in host byte order. None if ALL
        """
        if self._socket is not None:
            raise error.TestError('Raw socket already open')

        if protocol is None:
            self._socket = socket.socket(socket.PF_PACKET,
                                         socket.SOCK_RAW)

            self._socket.bind((self._name, self.ETH_P_ALL))
        else:
            self._socket = socket.socket(socket.PF_PACKET,
                                         socket.SOCK_RAW,
                                         socket.htons(protocol))
            self._socket.bind((self._name, self.ETH_P_ALL))

        self._socket.settimeout(1) # always running with 1 second timeout

    def close(self):
        """ Close the raw socket"""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        else:
            raise error.TestError('Raw socket not open')


    def recv(self, timeout):
        """Synchroneous receive.

        Receives one packet from the interface and returns its content
        in a string. Wait up to timeout for the packet if timeout is
        not 0. This function filters out all the packets that are
        less than the minimum ethernet packet size (60+crc).

        Args:
          timeout: max time in seconds to wait for the read to complete.
                   '0', wait for ever until a valid packet is received

        Returns:
          packet:    None no packet was received
                     a binary string containing the received packet.
          time_left: amount of time left in timeout
        """
        if self._socket is None:
            raise error.TestError('Raw socket not open')

        time_left = timeout
        packet = None
        while time_left or (timeout == 0):
            try:
                packet = self._socket.recv(ethernet.ETH_PACKET_MAX_SIZE)
                if len(packet) >= (ethernet.ETH_PACKET_MIN_SIZE-4):
                    break
                packet = None
                if timeout and time_left:
                    time_left -= raw_socket.SOCKET_TIMEOUT
            except socket.timeout:
                packet = None
                if timeout and time_left:
                    time_left -= raw_socket.SOCKET_TIMEOUT

        return packet, time_left


    def send(self, packet):
        """Send an ethernet packet."""
        if self._socket is None:
            raise error.TestError('Raw socket not open')

        self._socket.send(packet)


    def send_to(self, dst_mac, src_mac, protocol, payload):
        """Send an ethernet frame.

        Send an ethernet frame, formating the header.

        Args:
          dst_mac: 'byte string'
          src_mac: 'byte string'
          protocol: short in host byte order
          payload: 'byte string'
        """
        if self._socket is None:
            raise error.TestError('Raw socket not open')
        try:
            packet = ethernet.pack(dst_mac, src_mac, protocol, payload)
        except:
            raise error.TestError('Invalid Packet')
        self.send(packet)


    def recv_from(self, dst_mac, src_mac, protocol):
        """Receive an ethernet frame that matches the dst, src and proto.

        Filters all received packet to find a matching one, then unpack
        it and present it to the caller as a frame.

        Waits up to self._socket_timeout for a matching frame before
        returning.

        Args:
          dst_mac: 'byte string'. None do not use in filter.
          src_mac: 'byte string'. None do not use in filter.
          protocol: short in host byte order. None do not use in filter.

        Returns:
          ethernet frame: { 'dst' : byte string,
                            'src' : byte string,
                            'proto' : short in host byte order,
                            'payload' : byte string
                          }
        """
        start_time = time.clock()
        timeout = self._socket_timeout
        while 1:
            frame = None
            packet, timeout = self.recv(timeout)
            if packet is not None:
                frame = ethernet.unpack(packet)
                if ((src_mac is None or frame['src'] == src_mac) and
                    (dst_mac is None or frame['dst'] == dst_mac) and
                    (protocol is None or frame['proto'] == protocol)):
                    break;
                elif (timeout == 0 or
                      time.clock() - start_time > float(self._socket_timeout)):
                    frame = None
                    break
            else:
                if (timeout == 0 or
                    time.clock() - start_time > float(self._socket_timeout)):
                    frame = None
                    break
                continue

        return frame


class ethernet(object):
    """Provide ethernet packet manipulation methods."""
    HDR_LEN = 14     # frame header length
    CHECKSUM_LEN = 4 # frame checksum length

    # Ethernet payload types - http://standards.ieee.org/regauth/ethertype
    ETH_TYPE_IP        = 0x0800 # IP protocol
    ETH_TYPE_ARP       = 0x0806 # address resolution protocol
    ETH_TYPE_CDP       = 0x2000 # Cisco Discovery Protocol
    ETH_TYPE_8021Q     = 0x8100 # IEEE 802.1Q VLAN tagging
    ETH_TYPE_IP6       = 0x86DD # IPv6 protocol
    ETH_TYPE_LOOPBACK  = 0x9000 # used to test interfaces
    ETH_TYPE_LLDP      = 0x88CC # LLDP frame type

    ETH_PACKET_MAX_SIZE = 1518  # maximum ethernet frane size
    ETH_PACKET_MIN_SIZE = 64    # minimum ethernet frane size

    ETH_LLDP_DST_MAC = '01:80:C2:00:00:0E' # LLDP destination mac

    FRAME_KEY_DST_MAC = 'dst' # frame destination mac address
    FRAME_KEY_SRC_MAC = 'src' # frame source mac address
    FRAME_KEY_PROTO = 'proto' # frame protocol
    FRAME_KEY_PAYLOAD = 'payload' # frame payload


    def __init__(self):
        pass;


    @staticmethod
    def mac_string_to_binary(hwaddr):
        """Converts a MAC address text string to byte string.

        Converts a MAC text string from a text string 'aa:aa:aa:aa:aa:aa'
        to a byte string 'xxxxxxxxxxxx'

        Args:
          hwaddr: a text string containing the MAC address to convert.

        Returns:
          A byte string.
        """
        val = ''.join([chr(b) for b in [int(c, 16) \
                                        for c in hwaddr.split(':',6)]])
        return val


    @staticmethod
    def mac_binary_to_string(hwaddr):
        """Converts a MAC address byte string to text string.

        Converts a MAC byte string 'xxxxxxxxxxxx' to a text string
        'aa:aa:aa:aa:aa:aa'

        Args:
          hwaddr: a byte string containing the MAC address to convert.

        Returns:
         A text string.
        """
        return "%02x:%02x:%02x:%02x:%02x:%02x" % tuple(map(ord,hwaddr))


    @staticmethod
    def pack(dst, src, protocol, payload):
        """Pack a frame in a byte string.

        Args:
          dst: destination mac in byte string format
          src: src mac address in byte string format
          protocol: short in network byte order
          payload: byte string payload data

        Returns:
          An ethernet frame with header and payload in a byte string.
        """
        # numbers are converted to network byte order (!)
        frame = struct.pack("!6s6sH", dst, src, protocol) + payload
        return frame


    @staticmethod
    def unpack(raw_frame):
        """Unpack a raw ethernet frame.

        Returns:
          None on error
            { 'dst' : byte string,
              'src' : byte string,
              'proto' : short in host byte order,
              'payload' : byte string
            }
        """
        packet_len = len(raw_frame)
        if packet_len < ethernet.HDR_LEN:
            return None

        payload_len = packet_len - ethernet.HDR_LEN
        frame = {}
        frame[ethernet.FRAME_KEY_DST_MAC], \
        frame[ethernet.FRAME_KEY_SRC_MAC], \
        frame[ethernet.FRAME_KEY_PROTO] = \
            struct.unpack("!6s6sH", raw_frame[:ethernet.HDR_LEN])
        frame[ethernet.FRAME_KEY_PAYLOAD] = \
            raw_frame[ethernet.HDR_LEN:ethernet.HDR_LEN+payload_len]
        return frame


def ethernet_packet():
    try:
        from autotest_lib.client.bin.net import site_net_utils
        return site_net_utils.ethernet()
    except:
        return ethernet()
