'''
Autotest client/local option parser
'''

import sys, optparse

import common
from autotest_lib.client.bin.cmdparser import CommandParser


__all__ = ['AutotestLocalOptionParser']


class AutotestLocalOptionParser(optparse.OptionParser):
    '''
    Default autotest option parser
    '''
    def __init__(self):

        command_info = ('[command]\t\tOne of: %s' %
                        ", ".join(CommandParser.COMMAND_LIST))

        if sys.version_info[0:2] < (2, 6):
            optparse.OptionParser.__init__(
                self,
                usage = 'Usage: %prog [options] [command] <control-file>',
                description = command_info
                )
        else:
            optparse.OptionParser.__init__(
                self,
                usage = 'Usage: %prog [options] [command] <control-file>',
                epilog = command_info
                )


        self.add_option("-a", "--args", dest='args',
                          help="additional args to pass to control file")

        self.add_option("-c", "--continue", dest="cont",
                          action="store_true", default=False,
                          help="continue previously started job")

        self.add_option("-t", "--tag", dest="tag", type="string",
                          default="default",  help="set the job tag")

        self.add_option("-H", "--harness", dest="harness", type="string",
                          default='', help="set the harness type")

        self.add_option("-P", "--harness_args", dest="harness_args",
                        type="string", default='',
                        help="arguments delivered to harness")

        self.add_option("-U", "--user", dest="user", type="string",
                        default='', help="set the job username")

        self.add_option("-l", "--external_logging", dest="log",
                        action="store_true", default=False,
                        help="enable external logging")

        self.add_option('--verbose', dest='verbose', action='store_true',
                        help='Include DEBUG messages in console output')

        self.add_option('--quiet', dest='verbose', action='store_false',
                          help='Not include DEBUG messages in console output')

        self.add_option('--hostname', dest='hostname', type='string',
                        default=None, action='store',
                        help=('Take this as the hostname of this machine '
                              '(given by autoserv)'))

        self.add_option('--output_dir', dest='output_dir',
                        type='string', default="", action='store',
                        help=('Specify an alternate path to store test result '
                              'logs'))

        self.add_option('--client_test_setup', dest='client_test_setup',
                          type='string', default=None, action='store',
                          help=('a comma seperated list of client tests to '
                                'prebuild on the server. Use all to prebuild '
                                'all of them.'))

        self.add_option('--tap', dest='tap_report', action='store_true',
                          default=None, help='Output TAP (Test anything '
                          'protocol) reports')
