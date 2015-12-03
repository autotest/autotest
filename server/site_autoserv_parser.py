__author__ = "raphtee@google.com (Travis Miller)"

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.server.autoserv_parser import base_autoserv_parser


add_usage = """\
"""


class site_autoserv_parser(base_autoserv_parser):

    def get_usage(self):
        usage = super(site_autoserv_parser, self).get_usage()
        return usage + add_usage
