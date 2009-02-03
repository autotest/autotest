TYPE = 'BASIC'
CALIBRATION_JOB = ''

GLAG_FLAG = False
DEVICES = ['eth0']
CONNECTED_DEVICES = ['eth0']

NDLINK_SPEED = 1000
NDLINK_AUTONEG = True
NDLINK_RX = None
NDLINK_TX = False


FLOODPING_NUMPKTS = 100000
FLOODPING_CONSTRAINTS = ["rtt_max < 1.0",
                         "rtt_min < 0.05",
                         "rtt_avg < .06"
                        ]

PKT_SIZES = [64, 128, 256, 512, 1024, 1280, 1518]
PKTGEN_CONSTRAINTS = []

drives = ['hda']

IOBW_CONSTRAINTS = ["throughput > 500",
                    "read_bw > 100000",
                    "write_bw > 100000"]


NDTEST_TESTS = ['set_hwaddr',
                'set_maddr',
                'pkt_size',
                'zero_pad',
                'mac_filter',
                'multicast_filter',
                'broadcast',
                'promisc'
               ]


# list of ndlink tests
NDLINK_TESTS = ['carrier',
                'phy_config',
                'offload_config',
                'pause_config'
               ]

NETPERF_TESTS = {'TCP_STREAM': {'meas_streams': 16,
                                'constraints': ['Throughput > 800']
                               },
                 'TCP_SENDFILE': {'meas_streams': 16,
                                  'constraints': ['Throughput > 800']
                                 },
                 'UDP_STREAM': {'meas_streams': 16,
                                'constraints': ['Throughput > 500']
                               },
                 'UDP_RR': {'meas_streams': 16,
                            'constraints': ['Transfer_Rate > 1000']
                           },
                 'TCP_RR': {'meas_streams': 16,
                            'constraints': ['Transfer_Rate > 1000']
                           },
                 'TCP_CRR': {'meas_streams': 16,
                             'constraints': ['Transfer_Rate > 1000']
                            }
                }
