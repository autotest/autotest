import os, sys, getopt, optparse

from autotest_lib.client.common_lib import host_protections, utils


class base_autoserv_parser(object):
    """Custom command-line options parser for autoserv.

    We can't use the general getopt methods here, as there will be unknown
    extra arguments that we pass down into the control file instead.
    Thus we process the arguments by hand, for which we are duly repentant.
    Making a single function here just makes it harder to read. Suck it up.
    """
    def __init__(self):
        self.args = sys.argv[1:]
        self.parser = optparse.OptionParser()
        self.setup_options()
        self.parse_args()


    def setup_options(self):
        self.parser.add_option("-m", action="store", type="string",
                               dest="machines",
                               help="list of machines")
        self.parser.add_option("-M", action="store", type="string",
                               dest="machines_file",
                               help="list of machines from file")
        self.parser.add_option("-c", action="store_true",
                               dest="client", default=False,
                               help="control file is client side")
        self.parser.add_option("-s", action="store_true",
                               dest="server", default=False,
                               help="control file is server side")
        self.parser.add_option("-r", action="store", type="string",
                               dest="results", default=None,
                               help="specify results directory")
        self.parser.add_option("-l", action="store", type="string",
                               dest="label", default='',
                               help="label for the job")
        self.parser.add_option("-u", action="store", type="string",
                               dest="user",
                               default=os.environ.get('USER'),
                               help="username for the job")
        self.parser.add_option("-P", action="store", type="string",
                               dest="parse_job",
                               default='',
                               help="parse the results of the job")
        self.parser.add_option("-i", action="store_true",
                               dest="install_before", default=False,
                       help="reinstall machines before running the job")
        self.parser.add_option("-I", action="store_true",
                               dest="install_after", default=False,
                        help="reinstall machines after running the job")
        self.parser.add_option("-v", action="store_true",
                               dest="verify", default=False,
                               help="verify the machines only")
        self.parser.add_option("-R", action="store_true",
                               dest="repair", default=False,
                               help="repair the machines")
        self.parser.add_option("-C", "--cleanup", action="store_true",
                               default=False,
                               help="cleanup all machines after the job")
        self.parser.add_option("-n", action="store_true",
                               dest="no_tee", default=False,
                              help="no teeing the status to stdout/err")
        self.parser.add_option("-N", action="store_true",
                               dest="no_logging", default=False,
                              help="no logging")
        self.parser.add_option("-p", "--write-pidfile", action="store_true",
                               dest="write_pidfile", default=False,
                               help="write pidfile (.autoserv_execute)")
        protection_levels = [host_protections.Protection.get_attr_name(s)
                             for i, s in host_protections.choices]
        self.parser.add_option("--host-protection", action="store",
                               type="choice", dest="host_protection",
                               default=host_protections.default,
                               choices=protection_levels,
                               help="level of host protection during repair")
        self.parser.add_option("--ssh-user", action="store",
                               type="string", dest="ssh_user",
                               default="root",
                               help=("specify the user for ssh"
                               "connections"))
        self.parser.add_option("--ssh-port", action="store",
                               type="int", dest="ssh_port",
                               default=22,
                               help=("specify the port to use for "
                                     "ssh connections"))
        self.parser.add_option("--ssh-pass", action="store",
                               type="string", dest="ssh_pass",
                               default="",
                               help=("specify the password to use "
                                     "for ssh connections"))
        self.parser.add_option("--install-in-tmpdir", action="store_true",
                               dest="install_in_tmpdir", default=False,
                               help=("by default install autotest clients in "
                                     "a temporary directory"))


    def parse_args(self):
        (self.options, self.args) = self.parser.parse_args()


site_autoserv_parser = utils.import_site_class(
    __file__, "autotest_lib.server.site_autoserv_parser",
    "site_autoserv_parser", base_autoserv_parser)

class autoserv_parser(site_autoserv_parser):
    pass


# create the one and only one instance of autoserv_parser
autoserv_parser = autoserv_parser()
