import os, sys
try:
    import autotest.common as common
    rootdir = os.path.abspath(os.path.dirname(common.__file__))
    autodir = os.path.join(rootdir, 'client')
    autodirbin = os.path.join(rootdir, 'client', 'bin')
except ImportError:
    import common
    autodirbin = os.path.dirname(os.path.realpath(sys.argv[0]))
    autodir = os.path.dirname(autodirbin)
    sys.path.insert(0, autodirbin)

from autotest_lib.client.bin import job
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.bin import cmdparser, optparser

autodirtest = os.path.join(autodir, "tests")

os.environ['AUTODIR'] = autodir
os.environ['AUTODIRBIN'] = autodirbin
os.environ['AUTODIRTEST'] = autodirtest
os.environ['PYTHONPATH'] = autodirbin

opt_parser = optparser.AutotestLocalOptionParser()
cmd_parser = cmdparser.CommandParser() # Allow access to instance in parser

def usage():
    opt_parser.print_help()
    sys.exit(1)


def main():
    options, args = opt_parser.parse_args()
    args = cmd_parser.parse_args(args)

    # Check for a control file if not in prebuild mode.
    if len(args) != 1 and options.client_test_setup is None:
        print "Missing control file!"
        usage()

    drop_caches = global_config.global_config.get_config_value('CLIENT',
                                                               'drop_caches',
                                                               type=bool,
                                                               default=True)

    if options.client_test_setup:
        from autotest_lib.client.bin import setup_job
        exit_code = 0
        try:
            setup_job.setup_tests(options)
        except Exception:
            exit_code = 1
        sys.exit(exit_code)

    # JOB: run the specified job control file.
    job.runjob(os.path.realpath(args[0]), drop_caches, options)
