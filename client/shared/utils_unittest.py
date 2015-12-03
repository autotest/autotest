#!/usr/bin/python

import StringIO
import logging
import os
import socket
import subprocess
import unittest
import urllib2

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared.mock import MagicMock, patch
from autotest.client.shared import utils, autotemp
from autotest.client.shared.test_utils import mock


class test_read_one_line(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils, "open")

    def tearDown(self):
        self.god.unstub_all()

    def test_ip_to_long(self):
        self.assertEqual(utils.ip_to_long('0.0.0.0'), 0)
        self.assertEqual(utils.ip_to_long('255.255.255.255'), 4294967295)
        self.assertEqual(utils.ip_to_long('192.168.0.1'), 3232235521)
        self.assertEqual(utils.ip_to_long('1.2.4.8'), 16909320)

    def test_long_to_ip(self):
        self.assertEqual(utils.long_to_ip(0), '0.0.0.0')
        self.assertEqual(utils.long_to_ip(4294967295), '255.255.255.255')
        self.assertEqual(utils.long_to_ip(3232235521), '192.168.0.1')
        self.assertEqual(utils.long_to_ip(16909320), '1.2.4.8')

    def test_create_subnet_mask(self):
        self.assertEqual(utils.create_subnet_mask(0), 0)
        self.assertEqual(utils.create_subnet_mask(32), 4294967295)
        self.assertEqual(utils.create_subnet_mask(25), 4294967168)

    def test_format_ip_with_mask(self):
        self.assertEqual(utils.format_ip_with_mask('192.168.0.1', 0),
                         '0.0.0.0/0')
        self.assertEqual(utils.format_ip_with_mask('192.168.0.1', 32),
                         '192.168.0.1/32')
        self.assertEqual(utils.format_ip_with_mask('192.168.0.1', 26),
                         '192.168.0.0/26')
        self.assertEqual(utils.format_ip_with_mask('192.168.0.255', 26),
                         '192.168.0.192/26')

    def _create_test_file(self, contents):
        test_file = StringIO.StringIO(contents)
        utils.open.expect_call("filename", "r").and_return(test_file)

    def test_reads_one_line_file(self):
        self._create_test_file("abc\n")
        self.assertEqual("abc", utils.read_one_line("filename"))
        self.god.check_playback()

    def test_strips_read_lines(self):
        self._create_test_file("abc   \n")
        self.assertEqual("abc   ", utils.read_one_line("filename"))
        self.god.check_playback()

    def test_drops_extra_lines(self):
        self._create_test_file("line 1\nline 2\nline 3\n")
        self.assertEqual("line 1", utils.read_one_line("filename"))
        self.god.check_playback()

    def test_works_on_empty_file(self):
        self._create_test_file("")
        self.assertEqual("", utils.read_one_line("filename"))
        self.god.check_playback()

    def test_works_on_file_with_no_newlines(self):
        self._create_test_file("line but no newline")
        self.assertEqual("line but no newline",
                         utils.read_one_line("filename"))
        self.god.check_playback()

    def test_preserves_leading_whitespace(self):
        self._create_test_file("   has leading whitespace")
        self.assertEqual("   has leading whitespace",
                         utils.read_one_line("filename"))


class test_write_one_line(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils, "open")

    def tearDown(self):
        self.god.unstub_all()

    def get_write_one_line_output(self, content):
        test_file = mock.SaveDataAfterCloseStringIO()
        utils.open.expect_call("filename", "w").and_return(test_file)
        utils.write_one_line("filename", content)
        self.god.check_playback()
        return test_file.final_data

    def test_writes_one_line_file(self):
        self.assertEqual("abc\n", self.get_write_one_line_output("abc"))

    def test_preserves_existing_newline(self):
        self.assertEqual("abc\n", self.get_write_one_line_output("abc\n"))

    def test_preserves_leading_whitespace(self):
        self.assertEqual("   abc\n", self.get_write_one_line_output("   abc"))

    def test_preserves_trailing_whitespace(self):
        self.assertEqual("abc   \n", self.get_write_one_line_output("abc   "))

    def test_handles_empty_input(self):
        self.assertEqual("\n", self.get_write_one_line_output(""))


class test_open_write_close(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils, "open")

    def tearDown(self):
        self.god.unstub_all()

    def test_simple_functionality(self):
        data = "\n\nwhee\n"
        test_file = mock.SaveDataAfterCloseStringIO()
        utils.open.expect_call("filename", "w").and_return(test_file)
        utils.open_write_close("filename", data)
        self.god.check_playback()
        self.assertEqual(data, test_file.final_data)


class test_Statisctic(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)

    def tearDown(self):
        self.god.unstub_all()

    def test_simple_functionality(self):
        stat = utils.Statistic()
        stat.record(5)
        stat.record(15)
        stat.record(10)
        self.assertEqual(10, stat.get_average())
        self.assertEqual(5, stat.get_min())
        self.assertEqual(15, stat.get_max())


class test_ConvertDataSize(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)

    def tearDown(self):
        self.god.unstub_all()

    def test_simple_functionality(self):
        size = 12
        self.assertEqual(size, utils.convert_data_size('12'))
        size *= 1024
        self.assertEqual(size, utils.convert_data_size('12K'))
        size *= 1024
        self.assertEqual(size, utils.convert_data_size('12m'))
        size *= 1024
        self.assertEqual(size, utils.convert_data_size('12G'))
        size *= 1024
        self.assertEqual(size, utils.convert_data_size('12T'))


class test_read_keyval(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils, "open")
        self.god.stub_function(os.path, "isdir")
        self.god.stub_function(os.path, "exists")

    def tearDown(self):
        self.god.unstub_all()

    def _create_test_file(self, filename, contents):
        test_file = StringIO.StringIO(contents)
        os.path.exists.expect_call(filename).and_return(True)
        utils.open.expect_call(filename).and_return(test_file)

    def read_keyval(self, contents):
        os.path.isdir.expect_call("file").and_return(False)
        self._create_test_file("file", contents)
        keyval = utils.read_keyval("file")
        self.god.check_playback()
        return keyval

    def test_returns_empty_when_file_doesnt_exist(self):
        os.path.isdir.expect_call("file").and_return(False)
        os.path.exists.expect_call("file").and_return(False)
        self.assertEqual({}, utils.read_keyval("file"))
        self.god.check_playback()

    def test_accesses_files_directly(self):
        os.path.isdir.expect_call("file").and_return(False)
        self._create_test_file("file", "")
        utils.read_keyval("file")
        self.god.check_playback()

    def test_accesses_directories_through_keyval_file(self):
        os.path.isdir.expect_call("dir").and_return(True)
        self._create_test_file("dir/keyval", "")
        utils.read_keyval("dir")
        self.god.check_playback()

    def test_values_are_rstripped(self):
        keyval = self.read_keyval("a=b   \n")
        self.assertEquals(keyval, {"a": "b"})

    def test_comments_are_ignored(self):
        keyval = self.read_keyval("a=b # a comment\n")
        self.assertEquals(keyval, {"a": "b"})

    def test_integers_become_ints(self):
        keyval = self.read_keyval("a=1\n")
        self.assertEquals(keyval, {"a": 1})
        self.assertEquals(int, type(keyval["a"]))

    def test_float_values_become_floats(self):
        keyval = self.read_keyval("a=1.5\n")
        self.assertEquals(keyval, {"a": 1.5})
        self.assertEquals(float, type(keyval["a"]))

    def test_multiple_lines(self):
        keyval = self.read_keyval("a=one\nb=two\n")
        self.assertEquals(keyval, {"a": "one", "b": "two"})

    def test_the_last_duplicate_line_is_used(self):
        keyval = self.read_keyval("a=one\nb=two\na=three\n")
        self.assertEquals(keyval, {"a": "three", "b": "two"})

    def test_extra_equals_are_included_in_values(self):
        keyval = self.read_keyval("a=b=c\n")
        self.assertEquals(keyval, {"a": "b=c"})

    def test_non_alphanumeric_keynames_are_rejected(self):
        self.assertRaises(ValueError, self.read_keyval, "a$=one\n")

    def test_underscores_are_allowed_in_key_names(self):
        keyval = self.read_keyval("a_b=value\n")
        self.assertEquals(keyval, {"a_b": "value"})

    def test_dashes_are_allowed_in_key_names(self):
        keyval = self.read_keyval("a-b=value\n")
        self.assertEquals(keyval, {"a-b": "value"})


class test_write_keyval(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils, "open")
        self.god.stub_function(os.path, "isdir")

    def tearDown(self):
        self.god.unstub_all()

    def assertHasLines(self, value, lines):
        vlines = value.splitlines()
        vlines.sort()
        self.assertEquals(vlines, sorted(lines))

    def write_keyval(self, filename, dictionary, expected_filename=None,
                     type_tag=None):
        if expected_filename is None:
            expected_filename = filename
        test_file = StringIO.StringIO()
        self.god.stub_function(test_file, "close")
        utils.open.expect_call(expected_filename, "a").and_return(test_file)
        test_file.close.expect_call()
        if type_tag is None:
            utils.write_keyval(filename, dictionary)
        else:
            utils.write_keyval(filename, dictionary, type_tag)
        return test_file.getvalue()

    def write_keyval_file(self, dictionary, type_tag=None):
        os.path.isdir.expect_call("file").and_return(False)
        return self.write_keyval("file", dictionary, type_tag=type_tag)

    def test_accesses_files_directly(self):
        os.path.isdir.expect_call("file").and_return(False)
        result = self.write_keyval("file", {"a": "1"})
        self.assertEquals(result, "a=1\n")

    def test_accesses_directories_through_keyval_file(self):
        os.path.isdir.expect_call("dir").and_return(True)
        result = self.write_keyval("dir", {"b": "2"}, "dir/keyval")
        self.assertEquals(result, "b=2\n")

    def test_numbers_are_stringified(self):
        result = self.write_keyval_file({"c": 3})
        self.assertEquals(result, "c=3\n")

    def test_type_tags_are_excluded_by_default(self):
        result = self.write_keyval_file({"d": "a string"})
        self.assertEquals(result, "d=a string\n")
        self.assertRaises(ValueError, self.write_keyval_file,
                          {"d{perf}": "a string"})

    def test_perf_tags_are_allowed(self):
        result = self.write_keyval_file({"a{perf}": 1, "b{perf}": 2},
                                        type_tag="perf")
        self.assertHasLines(result, ["a{perf}=1", "b{perf}=2"])
        self.assertRaises(ValueError, self.write_keyval_file,
                          {"a": 1, "b": 2}, type_tag="perf")

    def test_non_alphanumeric_keynames_are_rejected(self):
        self.assertRaises(ValueError, self.write_keyval_file, {"x$": 0})

    def test_underscores_are_allowed_in_key_names(self):
        result = self.write_keyval_file({"a_b": "value"})
        self.assertEquals(result, "a_b=value\n")

    def test_dashes_are_allowed_in_key_names(self):
        result = self.write_keyval_file({"a-b": "value"})
        self.assertEquals(result, "a-b=value\n")


class test_is_url(unittest.TestCase):

    def test_accepts_http(self):
        self.assertTrue(utils.is_url("http://example.com"))

    def test_accepts_ftp(self):
        self.assertTrue(utils.is_url("ftp://ftp.example.com"))

    def test_rejects_local_path(self):
        self.assertFalse(utils.is_url("/home/username/file"))

    def test_rejects_local_filename(self):
        self.assertFalse(utils.is_url("filename"))

    def test_rejects_relative_local_path(self):
        self.assertFalse(utils.is_url("somedir/somesubdir/file"))

    def test_rejects_local_path_containing_url(self):
        self.assertFalse(utils.is_url("somedir/http://path/file"))


class test_urlopen(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)

    def tearDown(self):
        self.god.unstub_all()

    def stub_urlopen_with_timeout_comparison(self, test_func, expected_return,
                                             *expected_args):
        expected_args += (None,) * (2 - len(expected_args))

        def urlopen(url, data=None):
            self.assertEquals(expected_args, (url, data))
            test_func(socket.getdefaulttimeout())
            return expected_return
        self.god.stub_with(urllib2, "urlopen", urlopen)

    def stub_urlopen_with_timeout_check(self, expected_timeout,
                                        expected_return, *expected_args):
        def test_func(timeout):
            self.assertEquals(timeout, expected_timeout)
        self.stub_urlopen_with_timeout_comparison(test_func, expected_return,
                                                  *expected_args)

    def test_timeout_set_during_call(self):
        self.stub_urlopen_with_timeout_check(30, "retval", "url")
        retval = utils.urlopen("url", timeout=30)
        self.assertEquals(retval, "retval")

    def test_timeout_reset_after_call(self):
        old_timeout = socket.getdefaulttimeout()
        self.stub_urlopen_with_timeout_check(30, None, "url")
        try:
            socket.setdefaulttimeout(1234)
            utils.urlopen("url", timeout=30)
            self.assertEquals(1234, socket.getdefaulttimeout())
        finally:
            socket.setdefaulttimeout(old_timeout)

    def test_timeout_set_by_default(self):
        def test_func(timeout):
            self.assertTrue(timeout is not None)
        self.stub_urlopen_with_timeout_comparison(test_func, None, "url")
        utils.urlopen("url")

    def test_args_are_untouched(self):
        self.stub_urlopen_with_timeout_check(30, None, "http://url",
                                             "POST data")
        utils.urlopen("http://url", timeout=30, data="POST data")


class test_urlretrieve(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)

    def tearDown(self):
        self.god.unstub_all()

    def test_urlopen_passed_arguments(self):
        self.god.stub_function(utils, "urlopen")
        self.god.stub_function(utils.shutil, "copyfileobj")
        self.god.stub_function(utils, "open")

        url = "url"
        dest = "somefile"
        data = object()
        timeout = 10

        src_file = self.god.create_mock_class(file, "file")
        dest_file = self.god.create_mock_class(file, "file")

        (utils.urlopen.expect_call(url, data=data, timeout=timeout)
         .and_return(src_file))
        utils.open.expect_call(dest, "wb").and_return(dest_file)
        utils.shutil.copyfileobj.expect_call(src_file, dest_file)
        dest_file.close.expect_call()
        src_file.close.expect_call()

        utils.urlretrieve(url, dest, data=data, timeout=timeout)
        self.god.check_playback()


class test_merge_trees(unittest.TestCase):
    # a some path-handling helper functions

    def src(self, *path_segments):
        return os.path.join(self.src_tree.name, *path_segments)

    def dest(self, *path_segments):
        return os.path.join(self.dest_tree.name, *path_segments)

    def paths(self, *path_segments):
        return self.src(*path_segments), self.dest(*path_segments)

    def assertFileEqual(self, *path_segments):
        src, dest = self.paths(*path_segments)
        self.assertEqual(True, os.path.isfile(src))
        self.assertEqual(True, os.path.isfile(dest))
        self.assertEqual(os.path.getsize(src), os.path.getsize(dest))
        self.assertEqual(open(src).read(), open(dest).read())

    def assertFileContents(self, contents, *path_segments):
        dest = self.dest(*path_segments)
        self.assertEqual(True, os.path.isfile(dest))
        self.assertEqual(os.path.getsize(dest), len(contents))
        self.assertEqual(contents, open(dest).read())

    def setUp(self):
        self.src_tree = autotemp.tempdir(unique_id='utilsrc')
        self.dest_tree = autotemp.tempdir(unique_id='utilsdest')

        # empty subdirs
        os.mkdir(self.src("empty"))
        os.mkdir(self.dest("empty"))

    def tearDown(self):
        self.src_tree.clean()
        self.dest_tree.clean()

    def test_both_dont_exist(self):
        utils.merge_trees(*self.paths("empty"))

    def test_file_only_at_src(self):
        print >> open(self.src("src_only"), "w"), "line 1"
        utils.merge_trees(*self.paths("src_only"))
        self.assertFileEqual("src_only")

    def test_file_only_at_dest(self):
        print >> open(self.dest("dest_only"), "w"), "line 1"
        utils.merge_trees(*self.paths("dest_only"))
        self.assertEqual(False, os.path.exists(self.src("dest_only")))
        self.assertFileContents("line 1\n", "dest_only")

    def test_file_at_both(self):
        print >> open(self.dest("in_both"), "w"), "line 1"
        print >> open(self.src("in_both"), "w"), "line 2"
        utils.merge_trees(*self.paths("in_both"))
        self.assertFileContents("line 1\nline 2\n", "in_both")

    def test_directory_with_files_in_both(self):
        print >> open(self.dest("in_both"), "w"), "line 1"
        print >> open(self.src("in_both"), "w"), "line 3"
        utils.merge_trees(*self.paths())
        self.assertFileContents("line 1\nline 3\n", "in_both")

    def test_directory_with_mix_of_files(self):
        print >> open(self.dest("in_dest"), "w"), "dest line"
        print >> open(self.src("in_src"), "w"), "src line"
        utils.merge_trees(*self.paths())
        self.assertFileContents("dest line\n", "in_dest")
        self.assertFileContents("src line\n", "in_src")

    def test_directory_with_subdirectories(self):
        os.mkdir(self.src("src_subdir"))
        print >> open(self.src("src_subdir", "subfile"), "w"), "subdir line"
        os.mkdir(self.src("both_subdir"))
        os.mkdir(self.dest("both_subdir"))
        print >> open(self.src("both_subdir", "subfile"), "w"), "src line"
        print >> open(self.dest("both_subdir", "subfile"), "w"), "dest line"
        utils.merge_trees(*self.paths())
        self.assertFileContents("subdir line\n", "src_subdir", "subfile")
        self.assertFileContents("dest line\nsrc line\n", "both_subdir",
                                "subfile")


class test_get_relative_path(unittest.TestCase):

    def test_not_absolute(self):
        self.assertRaises(AssertionError, utils.get_relative_path, "a", "b")

    def test_same_dir(self):
        self.assertEqual(utils.get_relative_path("/a/b/c", "/a/b"), "c")

    def test_forward_dir(self):
        self.assertEqual(utils.get_relative_path("/a/b/c/d", "/a/b"), "c/d")

    def test_previous_dir(self):
        self.assertEqual(utils.get_relative_path("/a/b", "/a/b/c/d"), "../..")

    def test_parallel_dir(self):
        self.assertEqual(utils.get_relative_path("/a/c/d", "/a/b/c/d"),
                         "../../../c/d")


class test_sh_escape(unittest.TestCase):

    def _test_in_shell(self, text):
        escaped_text = utils.sh_escape(text)
        proc = subprocess.Popen(['/bin/bash', '-c', 'echo "%s"' % escaped_text],
                                stdin=open(os.devnull, 'r'),
                                stdout=subprocess.PIPE,
                                stderr=open(os.devnull, 'w'))
        stdout, _ = proc.communicate()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(stdout[:-1], text)

    def test_normal_string(self):
        self._test_in_shell('abcd')

    def test_spaced_string(self):
        self._test_in_shell('abcd efgh')

    def test_dollar(self):
        self._test_in_shell('$')

    def test_single_quote(self):
        self._test_in_shell('\'')

    def test_single_quoted_string(self):
        self._test_in_shell('\'efgh\'')

    def test_double_quote(self):
        self._test_in_shell('"')

    def test_double_quoted_string(self):
        self._test_in_shell('"abcd"')

    def test_backtick(self):
        self._test_in_shell('`')

    def test_backticked_string(self):
        self._test_in_shell('`jklm`')

    def test_backslash(self):
        self._test_in_shell('\\')

    def test_backslashed_special_characters(self):
        self._test_in_shell('\\$')
        self._test_in_shell('\\"')
        self._test_in_shell('\\\'')
        self._test_in_shell('\\`')

    def test_backslash_codes(self):
        self._test_in_shell('\\n')
        self._test_in_shell('\\r')
        self._test_in_shell('\\t')
        self._test_in_shell('\\v')
        self._test_in_shell('\\b')
        self._test_in_shell('\\a')
        self._test_in_shell('\\000')


class test_run(unittest.TestCase):

    """
    Test the utils.run() function.

    Note: This test runs simple external commands to test the utils.run()
    API without assuming implementation details.
    """

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils.logging, 'warn')
        self.god.stub_function(utils.logging, 'debug')

    def tearDown(self):
        self.god.unstub_all()

    def __check_result(self, result, command, exit_status=0, stdout='',
                       stderr=''):
        self.assertEquals(result.command, command)
        self.assertEquals(result.exit_status, exit_status)
        self.assertEquals(result.stdout, stdout)
        self.assertEquals(result.stderr, stderr)

    def test_default_simple(self):
        cmd = 'echo "hello world"'
        # expect some king of logging.debug() call but don't care about args
        utils.logging.debug.expect_any_call()
        self.__check_result(utils.run(cmd), cmd, stdout='hello world\n')

    def test_default_failure(self):
        cmd = 'exit 11'
        try:
            utils.run(cmd, verbose=False)
        except utils.error.CmdError, err:
            self.__check_result(err.result_obj, cmd, exit_status=11)

    def test_ignore_status(self):
        cmd = 'echo error >&2 && exit 11'
        self.__check_result(utils.run(cmd, ignore_status=True, verbose=False),
                            cmd, exit_status=11, stderr='error\n')

    def test_timeout(self):
        # we expect a logging.warn() message, don't care about the contents
        utils.logging.warn.expect_any_call()
        try:
            utils.run('echo -n output && sleep 10', timeout=1, verbose=False)
        except utils.error.CmdError, err:
            self.assertEquals(err.result_obj.stdout, 'output')

    def test_stdout_stderr_tee(self):
        cmd = 'echo output && echo error >&2'
        stdout_tee = StringIO.StringIO()
        stderr_tee = StringIO.StringIO()

        self.__check_result(utils.run(
            cmd, stdout_tee=stdout_tee, stderr_tee=stderr_tee,
            verbose=False), cmd, stdout='output\n', stderr='error\n')
        self.assertEqual(stdout_tee.getvalue(), 'output\n')
        self.assertEqual(stderr_tee.getvalue(), 'error\n')

    def test_stdin_string(self):
        cmd = 'cat'
        self.__check_result(utils.run(cmd, verbose=False, stdin='hi!\n'),
                            cmd, stdout='hi!\n')

    def test_safe_args(self):
        cmd = 'echo "hello \\"world" "again"'
        self.__check_result(utils.run(
            'echo', verbose=False, args=('hello "world', 'again')), cmd,
            stdout='hello "world again\n')

    def test_safe_args_given_string(self):
        cmd = 'echo "hello \\"world" "again"'
        self.assertRaises(TypeError, utils.run, 'echo', args='hello')


class test_compare_versions(unittest.TestCase):

    def test_zerofill(self):
        self.assertEqual(utils.compare_versions('1.7', '1.10'), -1)
        self.assertEqual(utils.compare_versions('1.222', '1.3'), 1)
        self.assertEqual(utils.compare_versions('1.03', '1.3'), 0)

    def test_unequal_len(self):
        self.assertEqual(utils.compare_versions('1.3', '1.3.4'), -1)
        self.assertEqual(utils.compare_versions('1.3.1', '1.3'), 1)

    def test_dash_delimited(self):
        self.assertEqual(utils.compare_versions('1-2-3', '1-5-1'), -1)
        self.assertEqual(utils.compare_versions('1-2-1', '1-1-1'), 1)
        self.assertEqual(utils.compare_versions('1-2-4', '1-2-4'), 0)

    def test_alphabets(self):
        self.assertEqual(utils.compare_versions('m.l.b', 'n.b.a'), -1)
        self.assertEqual(utils.compare_versions('n.b.a', 'm.l.b'), 1)
        self.assertEqual(utils.compare_versions('abc.e', 'abc.e'), 0)

    def test_mix_symbols(self):
        self.assertEqual(utils.compare_versions('k-320.1', 'k-320.3'), -1)
        self.assertEqual(utils.compare_versions('k-231.5', 'k-231.1'), 1)
        self.assertEqual(utils.compare_versions('k-231.1', 'k-231.1'), 0)

        self.assertEqual(utils.compare_versions('k.320-1', 'k.320-3'), -1)
        self.assertEqual(utils.compare_versions('k.231-5', 'k.231-1'), 1)
        self.assertEqual(utils.compare_versions('k.231-1', 'k.231-1'), 0)


class test_args_to_dict(unittest.TestCase):

    def test_no_args(self):
        result = utils.args_to_dict([])
        self.assertEqual({}, result)

    def test_matches(self):
        result = utils.args_to_dict(['aBc:DeF', 'SyS=DEf', 'XY_Z:',
                                     'F__o0O=', 'B8r:=:=', '_bAZ_=:=:'])
        self.assertEqual(result, {'abc': 'DeF', 'sys': 'DEf', 'xy_z': '',
                                  'f__o0o': '', 'b8r': '=:=', '_baz_': ':=:'})

    def test_unmatches(self):
        # Temporarily shut warning messages from args_to_dict() when an argument
        # doesn't match its pattern.
        logger = logging.getLogger()
        saved_level = logger.level
        logger.setLevel(logging.ERROR)

        try:
            result = utils.args_to_dict(['ab-c:DeF', '--SyS=DEf', 'a*=b', 'a*b',
                                         ':VAL', '=VVV', 'WORD'])
            self.assertEqual({}, result)
        finally:
            # Restore level.
            logger.setLevel(saved_level)


class test_get_random_port(unittest.TestCase):

    def do_bind(self, port, socket_type, socket_proto):
        s = socket.socket(socket.AF_INET, socket_type, socket_proto)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        return s

    def test_get_port(self):
        for _ in xrange(100):
            p = utils.get_unused_port()
            s = self.do_bind(p, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            self.assert_(s.getsockname())
            s = self.do_bind(p, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.assert_(s.getsockname())


class test_VersionableClass(unittest.TestCase):

    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_function(utils.logging, 'warn')
        self.god.stub_function(utils.logging, 'debug')
        self.version = 1

    def tearDown(self):
        self.god.unstub_all()

    class FooC(object):
        pass

    # Not implemented get_version -> not used for versioning.
    class VCP(FooC, utils.VersionableClass):

        def __new__(cls, *args, **kargs):
            test_VersionableClass.VCP.version = 1       # Only for unittesting.
            test_VersionableClass.VCP.master_class = test_VersionableClass.VCP
            return (super(test_VersionableClass.VCP, cls)
                    .__new__(cls, *args, **kargs))

        def foo(self):
            pass

    class VC2(VCP, utils.VersionableClass):

        @classmethod
        def get_version(cls):
            return cls.version

        @classmethod
        def is_right_version(cls, version):
            if version is not None:
                if version == 1:
                    return True
            return False

        def func1(self):
            logging.info("func1")

        def func2(self):
            logging.info("func2")

    # get_version could be inherited.
    class VC3(VC2, utils.VersionableClass):

        @classmethod
        def is_right_version(cls, version):
            if version is not None:
                if version == 2:
                    return True
            return False

        def func2(self):
            logging.info("func2_2")

    class PP(utils.VersionableClass):

        def __new__(cls, *args, **kargs):
            test_VersionableClass.PP.version = 1       # Only for unittesting.
            test_VersionableClass.PP.master_class = test_VersionableClass.PP
            return (super(test_VersionableClass.PP, cls)
                    .__new__(cls, *args, **kargs))

    class PP2(PP, utils.VersionableClass):

        @classmethod
        def get_version(cls):
            return cls.version

        @classmethod
        def is_right_version(cls, version):
            if version is not None:
                if cls.version == 1:
                    return True
            return False

        def func1(self):
            print "PP func1"

    class WP(utils.VersionableClass):

        def __new__(cls, *args, **kargs):
            test_VersionableClass.WP.version = 1       # Only for unittesting.
            test_VersionableClass.WP.master_class = test_VersionableClass.WP
            return (super(test_VersionableClass.WP, cls)
                    .__new__(cls, *args, **kargs))

    class WP2(WP, utils.VersionableClass):

        @classmethod
        def get_version(cls):
            return cls.version

        def func1(self):
            print "WP func1"

    class N(VCP, PP):
        pass

    class NN(N):
        pass

    class M(VCP):
        pass

    class MM(M):
        pass

    class W(WP):
        pass

    def test_simple_versioning(self):
        self.god.stub_function(test_VersionableClass.VCP, "foo")
        self.god.stub_function(test_VersionableClass.VC2, "func1")
        self.god.stub_function(test_VersionableClass.VC2, "func2")
        self.god.stub_function(test_VersionableClass.VC3, "func2")

        test_VersionableClass.VC2.func2.expect_call()
        test_VersionableClass.VC2.func1.expect_call()
        test_VersionableClass.VCP.foo.expect_call()
        test_VersionableClass.VC3.func2.expect_call()

        test_VersionableClass.VC2.func2.expect_call()
        test_VersionableClass.VC2.func1.expect_call()
        test_VersionableClass.VCP.foo.expect_call()
        test_VersionableClass.VC3.func2.expect_call()

        m = test_VersionableClass.M()
        m.func2()   # call VC3.func2(m)
        m.func1()   # call VC2.func1(m)
        m.foo()     # call VC1.foo(m)
        m.version = 2
        m.check_repair_versions()
        m.func2()

        mm = test_VersionableClass.MM()
        mm.func2()   # call VC3.func2(m)
        mm.func1()   # call VC2.func1(m)
        mm.foo()     # call VC1.foo(m)
        mm.version = 2
        mm.check_repair_versions()
        mm.func2()

        self.god.check_playback()

    def test_set_class_priority(self):
        self.god.stub_function(test_VersionableClass.VC2, "func1")
        self.god.stub_function(test_VersionableClass.VC2, "func2")
        self.god.stub_function(test_VersionableClass.VC3, "func2")
        self.god.stub_function(test_VersionableClass.PP2, "func1")

        test_VersionableClass.VC2.func1.expect_call()
        test_VersionableClass.PP2.func1.expect_call()
        test_VersionableClass.VC3.func2.expect_call()
        test_VersionableClass.PP2.func1.expect_call()
        test_VersionableClass.VC2.func1.expect_call()
        test_VersionableClass.VC2.func2.expect_call()

        m = test_VersionableClass.N()
        m.func1()
        m.set_priority_class(test_VersionableClass.PP,
                             [test_VersionableClass.PP,
                              test_VersionableClass.VCP])
        m.func1()

        m.version = 2
        m.check_repair_versions()
        m.func2()
        m.func1()

        m.set_priority_class(test_VersionableClass.VCP,
                             [test_VersionableClass.PP,
                              test_VersionableClass.VCP])

        m.func1()

        m.version = 1
        m.check_repair_versions()
        m.func2()

        self.god.check_playback()

    def test_set_class_priority_deep(self):
        self.god.stub_function(test_VersionableClass.VC2, "func1")
        self.god.stub_function(test_VersionableClass.VC2, "func2")
        self.god.stub_function(test_VersionableClass.VC3, "func2")
        self.god.stub_function(test_VersionableClass.PP2, "func1")

        test_VersionableClass.VC2.func1.expect_call()
        test_VersionableClass.PP2.func1.expect_call()
        test_VersionableClass.VC3.func2.expect_call()
        test_VersionableClass.PP2.func1.expect_call()
        test_VersionableClass.VC2.func1.expect_call()
        test_VersionableClass.VC2.func2.expect_call()

        m = test_VersionableClass.NN()
        m.func1()
        m.set_priority_class(test_VersionableClass.PP,
                             [test_VersionableClass.PP,
                              test_VersionableClass.VCP])
        m.func1()

        m.version = 2
        m.check_repair_versions()
        m.func2()
        m.func1()

        m.set_priority_class(test_VersionableClass.VCP,
                             [test_VersionableClass.PP,
                              test_VersionableClass.VCP])

        m.func1()

        m.version = 1
        m.check_repair_versions()
        m.func2()

        self.god.check_playback()

    def test_check_not_implemented(self):
        m = test_VersionableClass.W()
        self.assertEqual(m.__class__.__bases__,
                         tuple([test_VersionableClass.WP2]),
                         "Class should be WP2 (last defined class in class"
                         " hierarchy).")


class test_AsyncJob(unittest.TestCase):

    @staticmethod
    def make_thread_mock():
        class ThreadMock(object):

            def __init__(self, *args, **kwargs):
                self.daemon = False
                self.args = args
                self.kwargs = kwargs

            def start(self):
                self.start_called = True

        return ThreadMock

    def test_drainer(self):
        output = MagicMock()
        outputs = [output]
        read_values = ['asdf', '']

        def pop_values(*args):
            return read_values.pop(0)
        read_mock = MagicMock(side_effect=pop_values)

        @patch("os.read", read_mock)
        def _():
            utils.AsyncJob._fd_drainer(MagicMock(), outputs, MagicMock())
        _()

    def test_init_stdin_is_None(self):
        @patch.object(utils, "Thread")
        @patch.object(utils, "Lock")
        @patch("subprocess.Popen")
        def _(lock_mock, thread_mock, popen_mock):
            job = utils.AsyncJob("command", stdin=None)
            assert lock_mock.called
            assert thread_mock.called
            assert not hasattr(job, "stdin_thread")
            assert not hasattr(job, "stdin_lock")
            assert job.string_stdin is None
        _()

    def test_init_stdin_is_string(self):

        @patch.object(utils, "Thread", new_callable=self.make_thread_mock)
        @patch.object(utils, "Lock")
        @patch("subprocess.Popen")
        def _(lock_mock, thread_mock, popen_mock):
            job = utils.AsyncJob("echo", stdin="foobar")
            assert lock_mock.called
            assert job.stdin_thread.kwargs['name'] == 'echo-stdin'
            assert job.stdin_thread.kwargs['args'][0] == 'foobar'
            assert hasattr(job, "stdin_thread")
            assert hasattr(job, "stdin_lock")
            assert job.string_stdin is None
        _()

    def test_init_stdin_is_file(self):
        @patch.object(utils, "Thread", new_callable=self.make_thread_mock)
        @patch.object(utils, "Lock")
        @patch("subprocess.Popen")
        def _(lock_mock, thread_mock, popen_mock):
            job = utils.AsyncJob("echo", stdin=MagicMock(spec=file))
            assert lock_mock.called
            assert job.stdout_thread.kwargs['name'] == 'echo-stdout'
            assert job.stderr_thread.kwargs['name'] == 'echo-stderr'
            assert hasattr(job, "stdout_thread")
            assert hasattr(job, "stdout_lock")
            assert hasattr(job, "stderr_thread")
            assert hasattr(job, "stderr_lock")
            assert job.string_stdin is None
        _()

if __name__ == "__main__":
    unittest.main()
