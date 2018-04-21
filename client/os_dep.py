#!/usr/bin/env python

#  Copyright(c) 2013-2015 Intel Corporation.
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms and conditions of the GNU General Public License,
#  version 2, as published by the Free Software Foundation.
#
#  This program is distributed in the hope it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
#  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
#  more details.
#
#  You should have received a copy of the GNU General Public License along with
#  this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin St - Fifth Floor, Boston, MA 02110-1301 USA.
#
#  The full GNU General Public License is included in this distribution in
#  the file called "COPYING".


import itertools
import logging
import os
from glob import glob

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

try:
    next(iter(''), '')
except NameError:
    from autotest.client.shared.backports import next

# One day, when this module grows up, it might actually try to fix things.
# 'apt-cache search | apt-get install' ... or a less terrifying version of
# the same. With added distro-independant pixie dust.

COMMON_BIN_PATHS = ("/usr/libexec", "/usr/local/sbin", "/usr/local/bin",
                    "/usr/sbin", "/usr/bin", "/sbin", "/bin")


def exception_when_false_wrapper(func, exception_class, value_error_message_template):
    """
    Wrap a function to raise an exception when the return value is not True.

    :param func: function to wrap
    :type func: function
    :param exception_class: exception class to raise
    :type exception_class: Exception
    :param value_error_message_template: string to pass to exception
    :type value_error_message_template: str
    :return: wrapped function
    :rtype: function
    :raise exception_class: when func returns not true
    """

    def g(target, *args, **kwargs):
        val = func(target, *args, **kwargs)
        if val:
            return val
        else:
            raise exception_class(value_error_message_template % target)
    g.__name__ = func.__name__
    g.__doc__ = func.__doc__
    return g


def path_joiner(target, search_paths):
    """
    Create a generator that joins target to each search path

    :param target: filename to join to each search path
    :type target: str
    :param search_paths: iterator over all the search paths
    :type search_paths: iterator
    :return: iterator over all the joined paths
    :rtype: iterator
    """
    return (os.path.join(path, target) for path in search_paths)


def is_file_and_rx(pth):
    """
    :param pth: path to check
    :return: true if the path is a file and R_OK & X_OK
    :rtype: bool
    """
    return os.path.isfile(pth) and os.access(pth, os.R_OK & os.X_OK)


def is_file_and_readable(pth):
    """
    :param pth: path to check
    :return: true if the path is a file and R_OK
    :rtype: bool
    """
    return os.path.isfile(pth) and os.access(pth, os.R_OK)


def make_path_searcher(path_generator, target_predicate, target_normalizer, extra_paths, **kwargs):
    """
    Universal search function generator using lazy evaluation.

    Generate a function that will iterate over all the paths from path_generator using
    target_predicate to filter matching paths.  Each matching path is then noramlized by target_predicate.
    Only the first match is returned.

    :param path_generator: all paths to test with target_predicate
    :type path_generator: iterator
    :param target_predicate: boolean function that tests a given path
    :type target_predicate: function
    :param target_normalizer: function that transforms a matching path to some noramlized form
    :type target_normalizer: function
    :param extra_paths: extra paths to pass to the path_generator
    :type extra_paths: iterator
    :return: the path searching function
    :rtype:  function
    """

    def path_searcher(target, extra_dirs=extra_paths):
        matches = itertools.ifilter(
            target_predicate, path_generator(target, extra_dirs, **kwargs))
        paths = itertools.imap(target_normalizer, matches)
        return next(paths, '')
    return path_searcher


def unique_not_false_list(arg_paths):
    # probably better than an ordered dict or ordered set
    included = set()
    # preserve ordering while filtering out duplicates
    search_paths = []
    for p in arg_paths:
        # remove any empty paths
        if p and p not in included:
            included.add(p)
            search_paths.append(p)
    return search_paths


def generate_bin_search_paths(program, extra_dirs):
    """
    Generate full paths of potential locations of a given binary file based on
    COMMON_BIN_PATHS.

    Use the enviroment variable $PATH seed the list of search directories.

    :param program: library filename to join with all search directories
    :type program: str
    :param extra_dirs: extra directories to append to the directory search list
    :type extra_dirs: str
    :return: iterator over all generated paths
    :rtype: iter
    """
    # relative paths are accepted so don't use os.path.isabs()
    if os.sep in program:
        # if program already contains path then only check that path
        # e.g. `which bin/more` will succeed from /
        paths = [program]
    else:
        # `which` fails if PATH is empty, replicate this by returning '' when PATH is empty
        # such that ''.split(os.pathsep) == [''] which is filtered out
        arg_paths = itertools.chain(
            os.environ.get('PATH', '').split(os.pathsep), extra_dirs)
        # remove any empty paths and duplicates
        search_paths = unique_not_false_list(arg_paths)
        paths = path_joiner(program, search_paths)
    return paths


which = make_path_searcher(
    generate_bin_search_paths, is_file_and_rx, os.path.abspath, COMMON_BIN_PATHS)
which.__name__ = "which"
which.__doc__ = """
Find a program by searching in the environment path and in common binary paths.

check both if it is a file and executable
`which` always returns the abspath
return '' if failure because '' is well-defined NULL path, so it is
better than None or ValueError

:param program: command name or path to command
:type program: str
:param extra_dirs: iterable of extra paths to search
:type extra_dirs: iterble
:return: abspath of command if found, else ''
:rtype: str
"""

command = exception_when_false_wrapper(
    which, ValueError, 'Missing command: %s')
command.__name__ = "command"
command.__doc__ = """
Find a program by searching in the environment path and in common binary paths.

check both if it is a file and executable
`which` always returns the abspath
return '' if failure because '' is well-defined NULL path, so it is
better than None or ValueError

:param program: command name or path to command
:type program: str
:param extra_dirs: iterable of extra paths to search
:type extra_dirs: iterable
:return: abspath of command if found
:rtype: str
:exception ValueError: when program not found
"""


def commands(*cmds):
    return [command(c) for c in cmds]


# Don't be smart and try to guess the architecture because we could be
# on a multi-arch system
COMMON_LIB_BASE_PATHS = ['/lib', '/usr/lib', '/lib64', '/usr/lib64']
# the TLS hwcap is always added by ldconfig, so pre-generate the tls paths
# ldconfig.c:1276:   hwcap_extra[63 - _DL_FIRST_EXTRA] = "tls";
COMMON_LIB_TLS_PATHS = [os.path.join(p, 'tls') for p in COMMON_LIB_BASE_PATHS]
# convert to tuple so when used as default argument it is not mutable
COMMON_LIB_PATHS = tuple(COMMON_LIB_BASE_PATHS + COMMON_LIB_TLS_PATHS)


class Ldconfig(object):

    LD_SO_CONF = "/etc/ld.so.conf"
    MAX_RECURSION_DEPTH = 20

    class DirEntry(object):

        def __init__(self, path, flag, ino, dev):
            """
            Replica of ldconfig.c struct dir_entry.  Meant to hold ldconfig directories.
            In order to detect duplicates the inode and device number are compared on insert.
            /* List of directories to handle.  */
            struct dir_entry
            {
              char *path;
              int flag;
              ino64_t ino;
              dev_t dev;
              struct dir_entry *next;
            };
            :param path: library path
            :type path: str
            :param flag: string like 'libc4','libc5', 'libc6', 'glibc2'
            :type flag: str
            :param ino: inode number
            :type ino: int
            :param dev: id of device containing file
            :type dev: long
            """
            self.path = path
            self.flag = flag
            self.ino = ino
            self.dev = dev

        def __eq__(self, other):
            """
            Compare DirEntry based only on inode and device number

            :param other: other DirEntry
            :type other: DirEntry
            :return: True iff ino and dev are equal
            :rtype: bool
            """
            return self.ino == other.ino and self.dev == other.dev

        def __ne__(self, other):
            return not self == other

        def __repr__(self):
            return self.__class__.__name__ + "(%(path)r, %(flag)r, %(ino)r, %(dev)r)" % vars(self)

    def __init__(self):
        """
        This class is meant duplicate the behaviour of ldconfig and parse
        /etc/ld.so.conf and all the related config files Since the only specification
        for ldconfig is in the source code, this class is as much as possible a
        line-by-line direct translation from the C to Python.

        Currently we attempt to preserve the following behaviours, with caveats

        * include parsing is recursive, included files can include /etc/ld.so.conf,
          ldconfig.c has it's recursion depth limited by the process max file open
          limit.  We artifically limit the recursion depth to MAX_RECURSION_DEPTH

        * The library type suffix, .e.g. '/usr/lib/foo=glibc2' is correctly parsed and
          stored.  There can be any amount of whitespace between the end of the path
          and the type suffix.  We do not overwrite duplicate paths with new flag
          information.

        * hwcap is currently ignored.  Ideally we would parse the hwcap and add those
          directories to the search path based on runtime parsing of the HW
          capabilities set in /proc/cpuinfo, but that is not implemented.

        * The hardcoded hwcap of 'tls' is added to COMMON_LIB_PATHS during runtime
          constant definition.  This means we search /usr/lib64/tls by default.

        This current translation is based on elf/ldconfig.c from glibc-2.16-34.fc18.src.rpm

        """
        self.lddirs = []

    def _parse_config_line(self, config_file, filename, recursion):
        for line in config_file:
            line = line.strip()
            line = line.split('#')[0]
            if not line:
                continue
            # hardcoded to 'include' + space
            if line.startswith('include '):
                glob_patterns = line.split('include ')[1]
                # include supports multiple files split by whitespace
                for glob_pattern in glob_patterns.split():
                    self._parse_conf_include(
                        filename, glob_pattern, recursion)
            # hardcoded to 'hwcap' + space
            elif line.startswith("hwcap "):
                # ignore hwcap lines, but they do point to alternate directories
                # based on runtime processor capabilities in /proc/cpuinfo
                # .e.g. hwcap 0 nosegneg would add /lib/i686/nosegneg/libc.so.6
                continue
            else:
                self._add_dir(line)

    def parse_conf(self, filename=LD_SO_CONF, recursion=0):
        # print(filename)
        if recursion < self.MAX_RECURSION_DEPTH:
            # read lddirs from  main ld.so.conf file
            try:
                config_file = open(filename, 'r')
            except IOError:
                return
            try:
                self._parse_config_line(config_file, filename, recursion)
            finally:
                config_file.close()

    def _parse_conf_include(self, filename, glob_pattern, recursion):
        # os.path.dirname will succeed if os.sep is in filename
        if not os.path.isabs(glob_pattern) and os.sep in filename:
            # prepend with dirname of filename, e.g. /etc if /etc/ld.so.conf
            glob_pattern = os.path.join(
                os.path.dirname(filename), glob_pattern)
        glob_result = glob(glob_pattern)
        for conf_file in glob_result:
            # increment recusion so can limit depth
            self.parse_conf(conf_file, recursion + 1)

    def _add_single_dir(self, new_dir_entry):
        if new_dir_entry in self.lddirs:
            logging.debug("Path %s given more than once", new_dir_entry.path)
        else:
            self.lddirs.append(new_dir_entry)

    def _add_dir(self, line):
        # extract lib_type suffix, e.g. 'dirname=TYPE' where TYPE is in 'libc4',
        # 'libc5', 'libc6', 'glibc2'
        if '=' in line:
            path, flag = line.split('=', 1)
        else:
            path = line
            flag = ''
        path = path.rstrip()
        path = path.rstrip(os.sep)
        try:
            stat = os.stat(path)
            de = Ldconfig.DirEntry(path, flag, stat.st_ino, stat.st_dev)
            self._add_single_dir(de)
        except (IOError, OSError):
            logging.debug("Can't stat %s", path)

    def ldconfig(self, ld_so_conf_filename=LD_SO_CONF, extra_dirs=COMMON_LIB_PATHS):
        """
        Read and parse /etc/ld.so.conf to generate a list of directories that ldconfig would search.
        Pre-seed the search directory list with ('/lib', '/usr/lib', '/lib64', '/usr/lib64')

        :param ld_so_conf_filename: path to /etc/ld.so.conf
        :type ld_so_conf_filename: str
        :param extra_dirs:
        :type extra_dirs: iterable
        :return: iterator over the directories found
        :rtype: iterable
        """
        self.lddirs = []
        for d in extra_dirs:
            self._add_dir(d)
        self.parse_conf(ld_so_conf_filename)
        # only return the paths
        return (ld.path for ld in self.lddirs)


def generate_library_search_paths(lib, extra_dirs=COMMON_LIB_PATHS, ld_so_conf_filename=Ldconfig.LD_SO_CONF):
    """
    Generate full paths of potential locations of a given library file based on
    COMMON_LIB_PATHS.

    :param lib: library filename to join with all search directories
    :type lib: str
    :param extra_dirs: extra directories to append to the directory search list
    :type extra_dirs: iterable
    :param ld_so_conf_filename: location of /etc/ld.so.conf to parse to find all system library locations
    :type ld_so_conf_filename: str
    :return: iterator over all generated paths
    :rtype: iterable
    """
    if os.sep in lib:
        # is program already contains path then only check that path
        paths = [lib]
    else:
        ldcfg = Ldconfig()
        search_paths = ldcfg.ldconfig(ld_so_conf_filename, extra_dirs)
        paths = path_joiner(lib, search_paths)

    return paths


which_library = make_path_searcher(
    generate_library_search_paths, is_file_and_readable, os.path.abspath, COMMON_LIB_PATHS)
which_library.__name__ = "which_library"
which_library.__doc__ = """
Find a library file by parsing /etc/ld.so.conf and also searcing in the common library search paths, %s

Check both if the library is a file and readable.

:param lib: library file or path to library file, e.g. libc.so.6
:type lib: str
:param extra_dirs: iterable of extra paths to search
:type extra_dirs: iterable
:return: abspath of library if found, else ''
:rtype: str
""" % str(COMMON_LIB_PATHS)

library = exception_when_false_wrapper(
    which_library, ValueError, 'Missing library: %s')
library.__name__ = "library"
library.__doc__ = """
Find a library file by parsing /etc/ld.so.conf and also searcing in the common library search paths, %s

Check both if the library is a file and readable.

:param lib: library file or path to library file, e.g. libc.so.6
:type lib: str
:param extra_dirs: iterable of extra paths to search
:type extra_dirs: iterable
:return: abspath of library if found
:rtype: str
:exception ValueError: when library is not found
""" % str(COMMON_LIB_PATHS)


def libraries(*libs):
    return [library(l) for l in libs]


COMMON_HEADER_PATHS = ('/usr/include', '/usr/local/include')


def generate_include_search_paths(hdr, extra_dirs):
    """
    Generate full paths of potential locations of a given header file based on
    COMMON_HEADER_PATHS.

    :param hdr: header filename to join with all search directories
    :type hdr: str
    :param extra_dirs: extra directories to append to the directory search list
    :type extra_dirs: iterable
    :return: iterator over all generated paths
    :rtype: iterable
    """
    if os.sep in hdr:
        # is program already contains path then only check that path
        paths = [hdr]
    else:
        # `which` fails if PATH is empty, replicate this by returning '' when PATH is empty
        # such that ''.split(os.pathsep) == [''] which is filtered out
        arg_paths = itertools.chain(COMMON_HEADER_PATHS, extra_dirs)
        # remove any empty paths and duplicates
        search_paths = unique_not_false_list(arg_paths)
        paths = path_joiner(hdr, search_paths)
        # `which` always returns the abspath
    return paths


which_header = make_path_searcher(
    generate_include_search_paths, is_file_and_readable, os.path.abspath, frozenset([]))
which_header.__name__ = "which_header"
which_header.__doc__ = """
Find a header file by searching in the common include search paths, %s

Check both if the header is a file and readable.

:param hdr: header file or path to header file, e.g. stdio.h
:type hdr: str
:param extra_dirs: iterable of extra paths to search
:type extra_dirs: iterable
:return: abspath of header if found, else ''
:rtype: str
""" % str(COMMON_HEADER_PATHS)

header = exception_when_false_wrapper(
    which_header, ValueError, 'Missing header: %s')
header.__name__ = "header"
header.__doc__ = """
Find a header file by searching in the common include search paths, %s

Check both if the header is a file and readable.

:param hdr: header file or path to header file, e.g. stdio.h
:type hdr: str
:param extra_dirs: iterable of extra paths to search
:type extra_dirs: iterable
:return: abspath of header if found
:rtype: str
:exception ValueError: when header is not found
""" % str(COMMON_HEADER_PATHS)


def headers(*hdrs):
    return [header(h) for h in hdrs]
