"""
Autotest command parser

@copyright: Don Zickus <dzickus@redhat.com> 2011
"""

import os, re, sys
from autotest.client import os_dep
from autotest.client.shared import global_config
from autotest.client.shared import base_packages, packages

GLOBAL_CONFIG = global_config.global_config

LOCALDIRTEST = "tests"
GLOBALDIRTEST = GLOBAL_CONFIG.get_config_value('COMMON',
                                               'test_dir',
                                                default="")

tmpdir = os.path.abspath(os.path.join('.', 'tmp'))

FETCHDIRTEST = GLOBAL_CONFIG.get_config_value('COMMON',
                                               'test_output_dir',
                                                default=tmpdir)
FETCHDIRTEST = os.path.join(FETCHDIRTEST, 'site_tests')

if not os.path.isdir(FETCHDIRTEST):
    os.makedirs(FETCHDIRTEST)

DEBUG = False


class CommandParser(object):
    """
    A client-side command wrapper for the autotest client.
    """

    COMMAND_LIST = ['help', 'list', 'run', 'fetch']

    @classmethod
    def _print_control_list(cls, pipe, path):
        """
        Print the list of control files available.

        @param pipe: Pipe opened to an output stream (may be a pager)
        @param path: Path we'll walk through
        """
        if not os.path.isdir(path):
            pipe.write("Test directory not available\n")
            return

        pipe.write(" %-50s %s\n" % ("[Control]", "[Description]"))
        # The strategy here is to walk the root directory
        # looking for "*control*" files in some directory
        # and printing them out
        for root, _, files in sorted(os.walk(path)):
            for name in files:
                if re.search("control", name):
                    # strip full path
                    basename = re.sub(path + "/", "", root)
                    text = "%s/%s" % (basename, name)
                    desc = "None"

                    if name == "control":
                        # Imply /control by listing only directory name
                        text = "%s" % basename

                    for line in open(root + "/" + name).readlines():
                        if re.match("NAME", line):
                            # We have a description line
                            desc = re.split("=\s*", line,
                                            maxsplit=1)[1].rstrip()
                            try:
                                desc = desc[1:-1]
                            except IndexError:
                                pass
                            break
                    pipe.write(' %-50s %s\n' % (text, desc))


    def is_url(self, url):
        """Return true if path looks like a URL"""
        return url.startswith('http://') or url.startswith('git://')

    def fetch(self, args):
        """
        fetch a remote control file or packages

        """
        if not len(args):
            self.help()

        url = args.pop(0)
        if not self.is_url(url):
            print "Not a remote url, nothing to fetch (%s)" % url
            self.help()

        if len(args):
            name = args.pop(0)
        else:
            name = ""

        print "fetching file %s:%s" % (url, name)
        autodir = os.path.abspath(os.environ['AUTODIR'])
        tmpdir = os.path.join(autodir, 'tmp')
        tests_out_dir = GLOBAL_CONFIG.get_config_value('COMMON',
                                                       'test_output_dir',
                                                       default=tmpdir)
        pkg_dir = os.path.join(tests_out_dir, 'packages')
        install_dir = os.path.join(FETCHDIRTEST, name)

        pkgmgr = packages.PackageManager(tests_out_dir,
            run_function_dargs={'timeout':3600})
        pkgmgr.install_pkg(name, 'test', pkg_dir, install_dir,
            repo_url=url)

        raise SystemExit(0)


    @classmethod
    def help(cls):
        """
        List the commands and their usage strings.

        @param args is not used here.
        """
        print "Commands:"
        print "fetch <url> [<file>]\tFetch a remote file/package and install it"
        print "\tgit://...:[<branch>] [<file/directory>]"
        print "\thttp://... [<file>]"
        print "help\t\t\tOutput a list of supported commands"
        print "list\t\t\tOutput a list of available tests"
        print "run <test> [<args>]\tFind given <test> in path and run with args"
        raise SystemExit(0)


    @classmethod
    def list_tests(cls):
        """
        List the available tests for users to choose from
        """
        # One favorite feature from git :-)
        try:
            less_cmd = os_dep.command('less')
            pipe = os.popen('%s -FRSX' % less_cmd, 'w')
        except ValueError:
            pipe = sys.stdout

        pipe.write("List of tests available\n")
        pipe.write("Unless otherwise specified, outputs imply /control files\n")
        pipe.write("\n")

        # Walk local ./tests directory
        dirtest = os.path.join(os.path.abspath(os.path.curdir), LOCALDIRTEST)
        # Don't repeat autodirtest results
        if not os.environ['AUTODIRTEST']:
            dirtest = os.environ['AUTODIRTEST']
            pipe.write("Local tests (%s)\n" % dirtest)
            cls._print_control_list(pipe, dirtest)
            pipe.write("\n")

        # Walk fetchdirtest directory
        if FETCHDIRTEST and os.path.isdir(FETCHDIRTEST):
            dirtest = FETCHDIRTEST
            pipe.write("Remotely fetched tests (%s)\n" % dirtest)
            cls._print_control_list(pipe, dirtest)
            pipe.write("\n")

        # Walk globaldirtests directory
        if GLOBALDIRTEST and os.path.isdir(GLOBALDIRTEST):
            dirtest = GLOBALDIRTEST
            pipe.write("Globally imported tests (%s)\n" % dirtest)
            cls._print_control_list(pipe, dirtest)
            pipe.write("\n")

        # Walk autodirtest directory
        dirtest = os.environ['AUTODIRTEST']
        pipe.write("Autotest prepackaged tests (%s)\n" % dirtest)
        cls._print_control_list(pipe, dirtest)

        pipe.close()
        raise SystemExit(0)


    def parse_args(self, args):
        """
        Process a client side command.

        @param args: Command line args.
        """
        if len(args) and args[0] in self.COMMAND_LIST:
            cmd = args.pop(0)
        else:
            # Do things the traditional way
            return args

        # List is a python reserved word
        if cmd == 'list':
            cmd = 'list_tests'
        try:
            try:
                args = getattr(self, cmd)(args)
            except TypeError:
                args = getattr(self, cmd)()
        except SystemExit, return_code:
            sys.exit(return_code.code)
        except Exception, error_detail:
            if DEBUG:
                raise
            sys.stderr.write("Command failed: %s -> %s\n" % (cmd, error_detail))
            self.help()
            sys.exit(1)

        # Args are cleaned up, return to process the traditional way
        return args


    def run(self, args):
        """
        Wrap args with a path and send it back to autotest.
        """
        if not len(args):
            self.help()

        test = args.pop(0)

        # Autotest works on control files
        if not re.search("control", test):
            test = test + "/control"

        localdir = os.path.join(os.path.abspath(os.path.curdir), LOCALDIRTEST)
        fetchdir = FETCHDIRTEST
        globaldir = GLOBALDIRTEST
        autodir = os.environ['AUTODIRTEST']

        for dirtest in [localdir, fetchdir, globaldir, autodir]:
            d = os.path.join(dirtest, test)
            if os.path.isfile(d):
                args.insert(0, d)
                return args

        print "Can not find test %s" % test
        raise SystemExit(1)
