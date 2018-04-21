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
import os
import sys
import unittest

from autotest.client import os_dep
from autotest.client.shared.mock import patch, MagicMock, call


def both_true(fun):
    return patch.object(sys.modules['os'].path, "isfile", return_value=True)(
        patch.object(sys.modules['os'], "access", return_value=True)(fun))


def is_not_file(fun):
    return patch.object(sys.modules['os'].path, "isfile", return_value=False)(
        patch.object(sys.modules['os'], "access", return_value=False)(fun))


def not_executable(fun):
    return patch.object(sys.modules['os'].path, "isfile", return_value=True)(
        patch.object(sys.modules['os'], "access", return_value=False)(fun))


def empty_path(fun):
    # delete path
    return patch.object(sys.modules['os'], "environ", {})(
        patch.object(sys.modules['os'].path, "isfile")(
            patch.object(sys.modules['os'], "access")(fun)))


class TestWhich(unittest.TestCase):

    @staticmethod
    def test_always_true():

        @both_true
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            assert which("more")
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_is_not_file():

        @is_not_file
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            assert not which("more")
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_not_executable():

        @not_executable
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            assert not which("more")
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_fail_if_empty_path_and_no_extra_dirs():

        # delete path
        @empty_path
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            assert not which("more", extra_dirs=[])
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_uses_default_extra_dirs():

        @empty_path
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            from autotest.client.os_dep import COMMON_BIN_PATHS
            assert which("more") in (os.path.abspath(os.path.join(p, "more"))
                                     for p in COMMON_BIN_PATHS)
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_uses_non_default_extra_dirs():

        # delete path
        @empty_path
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            assert os.path.abspath(os.path.join(os.sep, "nosuch", "more")) == \
                which("more", extra_dirs=[os.path.join(os.sep, "nosuch")])
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_resolves_based_on_cwd_if_contains_path():

        @both_true
        def _test(access_mock, isfile_mock):
            from autotest.client.os_dep import which
            assert os.path.join(os.getcwd(), "foo", "more") == which(
                os.path.join("foo", "more"))
        # pylint: disable=E1120
        _test()


class TestCommand(unittest.TestCase):

    @staticmethod
    def test_command_raises_value_error():
        @is_not_file
        def _test(*args):
            try:
                os_dep.command("nosuch")
                assert False
            except ValueError as e:
                assert "nosuch" in e.message
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_command_raises_value_error_on_unlikely_path():
        @is_not_file
        def _test(*args):
            try:
                os_dep.command("\1")
                assert False
            except ValueError as e:
                assert "\1" in e.message
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_command_success():
        @both_true
        def _test(*args):
            cat = os.path.abspath(os.path.join(os.sep, "bin", "cat"))
            assert cat == os_dep.command(cat)
        # pylint: disable=E1120
        _test()


class TestCommands(unittest.TestCase):

    @staticmethod
    def test_commands():
        @patch.object(os_dep, "command")
        def _test(command_mock):
            paths = ['/a', '/b', '/c']
            command_mock.side_effect = paths
            try:
                cmds = os_dep.commands('a', 'b', 'c')
                assert cmds == paths
            except ValueError as e:
                assert "nosuch" in e.message
        # pylint: disable=E1120
        _test()


class TestDirEntry(unittest.TestCase):

    @staticmethod
    def test_eq():
        a = os_dep.Ldconfig.DirEntry("a", "", 1, 2)
        aa = os_dep.Ldconfig.DirEntry("b", "", 1, 2)
        b = os_dep.Ldconfig.DirEntry("b", "", 2, 3)
        assert a == aa
        assert a != b


class TestLibrary(unittest.TestCase):

    @staticmethod
    def test_add_single_dir_reject_duplicates_same_path():
        ldconfig = os_dep.Ldconfig()
        a = os_dep.Ldconfig.DirEntry("a", "", 1, 2)
        ldconfig.lddirs = [a]
        ldconfig._add_single_dir(a)
        assert ldconfig.lddirs == [a]

    @staticmethod
    def test_add_single_dir_reject_duplicates_not_same_path():
        ldconfig = os_dep.Ldconfig()
        a = os_dep.Ldconfig.DirEntry("a", "", 1, 2)
        ldconfig.lddirs = [a]
        # rejects because ino and dev are the same
        ldconfig._add_single_dir(os_dep.Ldconfig.DirEntry("b", "", 1, 2))
        assert ldconfig.lddirs == [a]

    @staticmethod
    def test_add_single_dir_adds():
        ldconfig = os_dep.Ldconfig()
        a = os_dep.Ldconfig.DirEntry("a", "", 1, 2)
        b = os_dep.Ldconfig.DirEntry("b", "", 2, 3)
        ldconfig.lddirs = [a]
        ldconfig._add_single_dir(b)
        assert ldconfig.lddirs == [a, b]

    @staticmethod
    def test_add_dir_calls_stat():
        @patch.object(sys.modules['os'], "stat", side_effect={"asdf": MagicMock(st_ino=2, st_dev=2)}.get)
        def _test(stat_mock):
            from autotest.client.os_dep import Ldconfig
            ldconfig = Ldconfig()
            ldconfig._add_dir("asdf")
            assert ldconfig.lddirs[0] == Ldconfig.DirEntry("asdf", "", 2, 2)
            assert ldconfig.lddirs[0].path == "asdf"
            assert ldconfig.lddirs[0].flag == ""
            assert ldconfig.lddirs[0].ino == 2
            assert ldconfig.lddirs[0].dev == 2
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_add_dir_splits_on_eq():
        @patch.object(sys.modules['os'], "stat", side_effect={
            "asdf": MagicMock(st_ino=2, st_dev=2),
            "qwer": MagicMock(st_ino=3, st_dev=3)}.get)
        def _test(stat_mock):
            from autotest.client.os_dep import Ldconfig
            ldconfig = Ldconfig()
            ldconfig._add_dir("asdf=glibc2")
            assert ldconfig.lddirs[0] == Ldconfig.DirEntry("asdf", "glibc2", 2, 2)
            ldconfig._add_dir("qwer%s      =glibc2" % os.sep)
            assert ldconfig.lddirs[1] == Ldconfig.DirEntry("qwer", "glibc2", 3, 3)
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_add_dir_ignores_stat_ioerror():
        @patch.object(sys.modules['os'], "stat", side_effect=IOError)
        @patch.object(os_dep, "logging")
        def _test(logging_mock, stat_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig._add_dir("asdf")
            assert ldconfig.lddirs == []
            assert logging_mock.debug.called
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_add_dir_ignores_stat_oserror():
        @patch.object(sys.modules['os'], "stat", side_effect=OSError)
        @patch.object(os_dep, "logging")
        def _test(logging_mock, stat_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig._add_dir("asdf")
            assert ldconfig.lddirs == []
            assert logging_mock.debug.called
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_read_config_file():
        ldconfig = os_dep.Ldconfig()

        @patch.object(ldconfig, "_add_dir")
        @patch.object(ldconfig, "_parse_conf_include")
        def _test(parse_conf_include_mock, add_dir_mock):
            ldconfig._parse_config_line(["include foo", "  # comment", "",
                                         "hwcap 0 nosegneg", "asdf",
                                         "include *",
                                         "include glob1 glob2    glob3 \t \t \t glob4"], "filename", 55)
            assert add_dir_mock.call_args_list == [call("asdf")]
            assert parse_conf_include_mock.call_args_list == [call(
                "filename", "foo", 55),
                call(
                    "filename", "*", 55),
                call(
                    "filename", "glob1", 55),
                call(
                    "filename", "glob2", 55),
                call(
                    "filename", "glob3", 55),
                call(
                    "filename", "glob4", 55),
            ]
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_stops_at_max_recursion():
        @patch.object(os_dep, "open", create=True)
        def _test(open_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig.parse_conf("", ldconfig.MAX_RECURSION_DEPTH + 2)
            assert not open_mock.called
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_opens_mock():
        @patch.object(os_dep, "open", create=True)
        def _test(open_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig.parse_conf("")
            assert open_mock.called
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_ignores_open_exception():
        @patch.object(os_dep, "open", create=True, side_effect=IOError)
        def _test(open_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig.parse_conf("")
            assert open_mock.called
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_include_joins_when_given_relative_path_with_slash():
        @patch.object(os_dep, "glob", return_value=[])
        @patch.object(os_dep.Ldconfig, "parse_conf")
        def _test(parse_conf, glob_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig._parse_conf_include(os.path.join(os.sep, "etc", "ld.so.conf"),
                                         os.path.join("a", "b", "c"), 1)
            assert glob_mock.call_args_list == [
                call(os.path.join(os.path.join(os.sep, "etc"),
                                  os.path.join("a", "b", "c")))]
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_include_joins_when_given_relative_path():
        @patch.object(os_dep, "glob", return_value=[])
        @patch.object(os_dep.Ldconfig, "parse_conf")
        def _test(parse_conf, glob_mock):
            ldconfig = os_dep.Ldconfig()
            ldconfig._parse_conf_include(os.path.join(os.sep, "etc", "ld.so.conf"),
                                         "foo", 1)
            assert glob_mock.call_args_list == [
                call(os.path.join(os.path.join(os.sep, "etc"),
                                  "foo"))]
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_include_does_not_join_when_no_slash_in_filename():
        @patch.object(os_dep, "glob", return_value=[])
        def _test(glob_mock):
            ldconfig = os_dep.Ldconfig()

            @patch.object(ldconfig, "parse_conf")
            def _test2(parse_conf_mock):
                ldconfig._parse_conf_include("noslash", "foo", 1)
                assert glob_mock.call_args_list == [call("foo")]
            # pylint: disable=E1120
            _test2()
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_parse_conf_include_iterates_over_globs():
        @patch.object(os_dep, "glob", return_value=["a", "b", "c"])
        def _test(glob_mock):
            ldconfig = os_dep.Ldconfig()

            @patch.object(ldconfig, "parse_conf")
            def _test2(parse_conf_mock):
                ldconfig._parse_conf_include(
                    os.path.join(os.sep, "etc", "ld.so.conf"),
                    "foo", 1)
                assert glob_mock.call_args_list == [
                    call(os.path.join(os.sep, "etc", "foo"))]
                assert parse_conf_mock.call_args_list == [call(
                    "a", 2), call("b", 2),
                    call("c", 2)]
            # pylint: disable=E1120
            _test2()
        # pylint: disable=E1120
        _test()

# try:
#     import pytest
#
#     def make_it(tmpdir):
#         lib_dir = tmpdir.mkdir("lib")
#         lib1_dir = lib_dir.mkdir("lib1")
#         lib2_dir = lib_dir.mkdir("lib2")
#         lib3_dir = lib_dir.mkdir("lib3")
#         try:
#             # symlink lib4 to lib3 to test duplicate detection
#             lib_dir.join("lib4").mksymlinkto(lib3_dir, absolute=0)
#         except AttributeError:
#             # symlinks are ignored anyway so ignore failure to create
#             pass
#         t = tmpdir.mkdir("etc")
#         t.chdir()
#         ld_so_conf_dir = t.mkdir('ld.so.conf.d')
#         # recursion
#         ld_so_conf_dir.join('recurse.conf').write(
#             "include %s" % t.join("ld.so.conf"))
#         ld_so_conf_dir.join('type.conf').write("""%(0)s%(sep)s=glibc2
#     %(0)s     =glibc2
#     %(1)s%(sep)s   =glibc2
#     """ % {'0': lib1_dir, '1': lib2_dir, 'sep': os.sep})
#         ld_so_conf_dir.join('hwcap.conf').write("hwcap 0 nosegnet")
#         ld_so_conf_dir.join('comment.conf').write(
#             "# this is a comment\n%s # another comment" % lib3_dir)
#         t.join("ld.so.conf").write("include %s\n%s" %
#                                    (t.join("ld.so.conf.d", "*.conf"), lib_dir.join("lib4")))
#         return t
#
#     @pytest.mark.skipif("os.stat(__file__).st_ino == 0", reason="requires valid inode and device numbers")
#     def test_on_filesystem(tmpdir):
#         ld_so_conf_dir = make_it(tmpdir)
#         l = os_dep.Ldconfig()
#         paths = list(l.ldconfig(
#             str(ld_so_conf_dir.join("ld.so.conf")), extra_dirs=[]))
#         print
#         # for d in l.lddirs:
#         #     print(d)
#         assert l.lddirs[0].path.endswith("lib3")
#         assert l.lddirs[1].path.endswith("lib1")
#         assert l.lddirs[1].flag == "glibc2"
#         assert l.lddirs[2].path.endswith("lib2")
#         assert l.lddirs[2].flag == "glibc2"
#         assert paths[0].endswith("lib3")
#         assert paths[1].endswith("lib1")
#         assert paths[2].endswith("lib2")
#
#
# except ImportError:
#     pass


class TestUniqueList(unittest.TestCase):

    def test_unique_list(self):
        thous = range(1, 1000)
        lst = list(itertools.chain(thous, thous))
        assert thous == os_dep.unique_not_false_list(lst)
        lst = list(itertools.chain(thous, reversed(thous)))
        assert thous == os_dep.unique_not_false_list(lst)


class TestHeaders(unittest.TestCase):

    @staticmethod
    def test_header_raises_value_error():
        @is_not_file
        def _test(*args):
            try:
                os_dep.header("nosuch.h")
                assert False
            except ValueError as e:
                assert "nosuch.h" in e.message
        # pylint: disable=E1120
        _test()

    @staticmethod
    def test_success():

        @both_true
        def _test(*args):
            from autotest.client.os_dep import which_header
            assert which_header("stdio.h")
        # pylint: disable=E1120
        _test()


if __name__ == "__main__":
    unittest.main()
