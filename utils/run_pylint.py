#!/usr/bin/python -u

import os
import sys
import fnmatch

# do a basic check to see if pylint is even installed
try:
    from pylint.__pkginfo__ import version as pylint_version
except ImportError:
    print "Unable to import pylint, it may need to be installed"
    sys.exit(1)

# Classes of errors we ignore on quiet runs
IGNORED_ERRORS = 'E1002,E1101,E1103,E1120,F0401,I0011'
# By default, complain about all things
LINT_VERBOSE = True


def set_verbosity(verbose):
    '''
    Changes the verbosity level
    '''
    global LINT_VERBOSE
    LINT_VERBOSE = verbose

major, minor, _ = pylint_version.split('.')
pylint_version = float("%s.%s" % (major, minor))

# patch up the logilab module lookup tools to understand autotest.* trash
import logilab.common.modutils
_ffm = logilab.common.modutils.file_from_modpath


def file_from_modpath(modpath, path=None, context_file=None):
    if modpath[0] == "autotest":
        if modpath[1:]:
            return _ffm(modpath[1:], path, context_file)
    return _ffm(modpath, path, context_file)
logilab.common.modutils.file_from_modpath = file_from_modpath


import pylint.lint
from pylint.checkers import imports

ROOT_MODULE = 'autotest.'

# need to put autotest root dir on sys.path so pylint will be happy
autotest_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, autotest_root)

# patch up pylint import checker to handle our importing magic
RealImportsChecker = imports.ImportsChecker


class CustomImportsChecker(imports.ImportsChecker):

    def visit_from(self, node):
        if node.modname.startswith(ROOT_MODULE):
            node.modname = node.modname[len(ROOT_MODULE):]
        return RealImportsChecker.visit_from(self, node)

imports.ImportsChecker = CustomImportsChecker

# some files make pylint blow up, so make sure we ignore them
blacklist = ['/contrib/*', '/frontend/afe/management.py', ]


def get_pylint_opts():
    """
    If VERBOSE is set, show all complaints. If not, only errors.

    There are three major sources of E1103/E1120 false positives:
     * shared.enum.Enum objects
     * DB model objects (scheduler models are the worst, but Django models also
       generate some errors)
    """
    disable_new = ['--disable=W,R,C,%s' % IGNORED_ERRORS]
    disable_old = ['--disable-msg-cat=W,R,C', '--disable-msg=%s' %
                   IGNORED_ERRORS]
    if LINT_VERBOSE:
        opts = []
    else:
        if pylint_version >= 0.21:
            opts = disable_new
        else:
            opts = disable_old

    opts += ['--reports=no', '--rcfile=/dev/null',
             '--good-names=i,j,k,Run,_,vm']

    if pylint_version < 1.0:
        fmt_opt = '--include-ids=y'
    else:
        fmt_opt = '--msg-template="{msg_id}:{line:3d},{column}: {obj}: {msg}"'
    opts.append(fmt_opt)

    return opts


def check_file(file_path):
    if not file_path.endswith('.py'):
        return 0
    for blacklist_pattern in blacklist:
        if fnmatch.fnmatch(os.path.abspath(file_path),
                           '*' + blacklist_pattern):
            return 0
    pylint_opts = get_pylint_opts()
    if pylint_version >= 0.21:
        runner = pylint.lint.Run(pylint_opts + [file_path], exit=False)
    else:
        runner = pylint.lint.Run(pylint_opts + [file_path])

    return runner.linter.msg_status


def visit(arg, dirname, filenames):
    for filename in filenames:
        check_file(os.path.join(dirname, filename))


def check_dir(dir_path):
    os.path.walk(dir_path, visit, None)

if __name__ == "__main__":
    import optparse
    usage = "usage: %prog [options] [list of files]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-q", "--quiet",
                      action="store_true", dest="quiet",
                      help="Ignore pylint errors %s" % IGNORED_ERRORS)
    options, args = parser.parse_args()
    verbose = not options.quiet
    set_verbosity(verbose)
    file_list = args
    pylint_base_opts = get_pylint_opts()
    if '--' in file_list:
        index = file_list.index('--')
        pylint_base_opts.extend(file_list[index + 1:])
        file_list = file_list[:index]
    if len(file_list) > 0:
        for path in file_list:
            if os.path.isdir(path):
                check_dir(path)
            else:
                check_file(path)
    else:
        check_dir('.')
