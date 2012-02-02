#!/usr/bin/python -u

import os, sys, fnmatch
try:
    import autotest.common as common
except ImportError:
    import common

# do a basic check to see if pylint is even installed
try:
    import pylint
    from pylint.__pkginfo__ import version as pylint_version
except ImportError:
    print "Unable to import pylint, it may need to be installed"
    sys.exit(1)

major, minor, release = pylint_version.split('.')
pylint_version = float("%s.%s" % (major, minor))
pylintrc_path = os.path.expanduser('~/.pylintrc')
if not os.path.exists(pylintrc_path):
    open(pylintrc_path, 'w').close()


# patch up the logilab module lookup tools to understand autotest_lib.* trash
import logilab.common.modutils
_ffm = logilab.common.modutils.file_from_modpath
def file_from_modpath(modpath, path=None, context_file=None):
    if modpath[0] == "autotest_lib":
        return _ffm(modpath[1:], path, context_file)
    else:
        return _ffm(modpath, path, context_file)
logilab.common.modutils.file_from_modpath = file_from_modpath


import pylint.lint
from pylint.checkers import imports

ROOT_MODULE = 'autotest_lib.'

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
blacklist = ['/contrib/*', '/frontend/afe/management.py']

# only show errors
# there are three major sources of E1101/E1103/E1120 false positives:
# * common_lib.enum.Enum objects
# * DB model objects (scheduler models are the worst, but Django models also
#   generate some errors)
if pylint_version >= 0.21:
    pylint_base_opts = ['--disable=W,R,C,E1101,E1103,E1120,F0401']
else:
    pylint_base_opts = ['--disable-msg-cat=warning,refactor,convention',
                        '--disable-msg=E1101,E1103,E1120,F0401']
pylint_base_opts += ['--reports=no',
                     '--include-ids=y']

file_list = sys.argv[1:]
if '--' in file_list:
    index = file_list.index('--')
    pylint_base_opts.extend(file_list[index+1:])
    file_list = file_list[:index]


def check_file(file_path):
    if not file_path.endswith('.py'):
        return
    for blacklist_pattern in blacklist:
        if fnmatch.fnmatch(os.path.abspath(file_path),
                           '*' + blacklist_pattern):
            return
    pylint.lint.Run(pylint_base_opts + [file_path])


def visit(arg, dirname, filenames):
    for filename in filenames:
        check_file(os.path.join(dirname, filename))


def check_dir(dir_path):
    os.path.walk(dir_path, visit, None)


if len(file_list) > 0:
    for path in file_list:
        if os.path.isdir(path):
            check_dir(path)
        else:
            check_file(path)
else:
    check_dir('.')
