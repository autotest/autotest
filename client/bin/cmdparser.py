"""
Autotest command parser

@copyright: Don Zickus <dzickus@redhat.com> 2011
"""

import os, re, sys
from autotest_lib.client.bin import os_dep

LOCALDIRTEST = "tests"
GLOBALDIRTEST = "/opt/autotest/tests"
DEBUG = False


class CommandParser(object):
    """
    A client-side command wrapper for the autotest client.
    """

    COMMAND_LIST = ['help', 'list', 'run']

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


    @classmethod
    def help(cls):
        """
        List the commands and their usage strings.

        @param args is not used here.
        """
        print "Commands:"
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
        if not dirtest == os.environ['AUTODIRTEST']:
            pipe.write("Local tests (%s)\n" % dirtest)
            cls._print_control_list(pipe, dirtest)
            pipe.write("\n")

        # Walk globaldirtests directory
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
        globaldir = GLOBALDIRTEST
        autodir = os.environ['AUTODIRTEST']

        for dirtest in [localdir, globaldir, autodir]:
            if os.path.isfile(dirtest + "/" + test):
                args.insert(0, dirtest + "/" + test)
                return args

        print "Can not find test %s" % test
        raise SystemExit(1)
