'''
Autotest client/local option parser
'''

import sys
import optparse

from autotest.client.cmdparser import CommandParser


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
                usage='Usage: %prog [options] [command] <control-file>',
                description=command_info
            )
        else:
            optparse.OptionParser.__init__(
                self,
                usage='Usage: %prog [options] [command] <control-file>',
                epilog=command_info
            )

        general = optparse.OptionGroup(self, 'GENERAL JOB CONTROL')
        general.add_option("-a", "--args", dest='args',
                           help="additional args to pass to control file")

        general.add_option("-c", "--continue", dest="cont",
                           action="store_true", default=False,
                           help="continue previously started job")

        general.add_option("-H", "--harness", dest="harness", type="string",
                           default='', help="set the harness type")

        general.add_option("-P", "--harness_args", dest="harness_args",
                           type="string", default='',
                           help="arguments delivered to harness")

        general.add_option('--client_test_setup', dest='client_test_setup',
                           type='string', default=None, action='store',
                           help=('a comma separated list of client tests to '
                                 'prebuild on the server. Use all to prebuild '
                                 'all of them.'))
        general.add_option("-d",'--test_directory', dest='test_directory',
                           type='string', default=None, action='store',
                           help=('Specify a custom test directory '))
        self.add_option_group(general)

        job_id = optparse.OptionGroup(self, 'JOB IDENTIFICATION')
        job_id.add_option("-t", "--tag", dest="tag", type="string",
                          default="default", help="set the job tag")

        job_id.add_option('--hostname', dest='hostname', type='string',
                          default=None, action='store',
                          help=('Take this as the hostname of this machine '
                                '(given by autoserv)'))

        job_id.add_option("-U", "--user", dest="user", type="string",
                          default='', help="set the job username")
        self.add_option_group(job_id)

        verbosity = optparse.OptionGroup(self, 'VERBOSITY')
        verbosity.add_option('--verbose', dest='verbose', action='store_true',
                             default=False,
                             help='Include DEBUG messages in console output. '
                             'If omitted, only informational messages will be '
                             'shown.')
        self.add_option_group(verbosity)

        output = optparse.OptionGroup(self, 'OUTPUT LOCATION AND FORMAT')
        output.add_option("-l", "--external_logging", dest="log",
                          action="store_true", default=False,
                          help="Enable external logging. This only makes any "
                          "difference if you have a site_job.py file that "
                          "implements the custom logging functionality ")

        output.add_option('--output_dir', dest='output_dir',
                          type='string', default="", action='store',
                          help=('Specify an alternate path to store test result '
                                'logs'))

        output.add_option('--tap', dest='tap_report', action='store_true',
                          default=None, help='Output TAP (Test anything '
                          'protocol) reports')
        self.add_option_group(output)
