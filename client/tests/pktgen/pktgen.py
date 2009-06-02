import os, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class pktgen(test.test):
    version = 1

    def execute(self, eth='eth0', count=50000, clone_skb=1, \
                    dst_ip='192.168.210.210', dst_mac='01:02:03:04:05:07'):
        if not os.path.exists('/proc/net/pktgen'):
            utils.system('/sbin/modprobe pktgen')
        if not os.path.exists('/proc/net/pktgen'):
            raise error.TestError('pktgen not loaded')

        logging.info('Adding devices to run')
        self.pgdev = '/proc/net/pktgen/kpktgend_0'

        self.pgset('rem_device_all')
        self.pgset('add_device ' + eth)
        self.pgset('max_before_softirq 10000')

        # Configure the individual devices
        logging.info('Configuring devices')

        self.ethdev='/proc/net/pktgen/' + eth
        self.pgdev=self.ethdev

        if clone_skb:
            self.pgset('clone_skb %d' % (count))
        self.pgset('min_pkt_size 60')
        self.pgset('max_pkt_size 60')
        self.pgset('dst ' + dst_ip)
        self.pgset('dst_mac ' + dst_mac)
        self.pgset('count %d' % (count))

        # Time to run
        self.pgdev='/proc/net/pktgen/pgctrl'
        self.pgset('start')

        output = os.path.join(self.resultsdir, eth)
        utils.system ('cp %s %s' % (self.ethdev, output))


    def pgset(self, command):
        file = open(self.pgdev, 'w')
        file.write(command + '\n');
        file.close

        if not utils.grep('Result: OK', self.pgdev):
            if not utils.grep('Result: NA', self.pgdev):
                utils.system('cat ' + self.pgdev)
