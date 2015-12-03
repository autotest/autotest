import os
import sys
try:
    import autotest.common as common  # pylint: disable=W0611
    rootdir = os.path.abspath(os.path.dirname(common.__file__))
    autodir = os.path.join(rootdir, 'client')
    autodirbin = os.path.join(rootdir, 'client', 'bin')
except ImportError:
    import common  # pylint: disable=W0611
    autodirbin = os.path.realpath(sys.argv[0])
    autodir = os.path.dirname(autodirbin)
    sys.path.insert(0, autodirbin)

autodirtest = os.path.join(autodir, "tests")

os.environ['AUTODIR'] = autodir
os.environ['AUTODIRBIN'] = autodirbin
os.environ['AUTODIRTEST'] = autodirtest
os.environ['PYTHONPATH'] = autodirbin

from autotest.client import job
from autotest.client.shared.settings import settings
from autotest.client import cmdparser, optparser


class AutotestLocalApp:

    '''
    Autotest local app runs tests locally

    Point it to a control file and let it rock
    '''

    def __init__(self):
        self._set_parsers()

    def _set_parsers(self):
        self.opt_parser = optparser.AutotestLocalOptionParser()
        self.cmd_parser = cmdparser.CommandParser()

    def usage(self):
        self.opt_parser.print_help()
        sys.exit(1)

    def parse_cmdline(self):
        self.options, args = self.opt_parser.parse_args()

        if self.options.test_directory is not None:
            if os.path.isdir(self.options.test_directory):
                os.environ['CUSTOM_DIR'] = self.options.test_directory
            else:
                print "The custom directory specifed does not exist, ignoring it..."

        self.args = self.cmd_parser.parse_args(args, self.options)

        # Check for a control file if not in prebuild mode.
        if len(args) != 1 and self.options.client_test_setup is None:
            print "Missing control file!"
            self.usage()

    def main(self):
        self.parse_cmdline()

        drop_caches = settings.get_value('CLIENT', 'drop_caches', type=bool,
                                         default=True)

        if self.options.client_test_setup:
            from autotest.client import setup_job
            exit_code = 0
            try:
                setup_job.setup_tests(self.options)
            except Exception:
                exit_code = 1
            sys.exit(exit_code)

        # JOB: run the specified job control file.
        job.runjob(os.path.realpath(self.args[0]), drop_caches, self.options)
