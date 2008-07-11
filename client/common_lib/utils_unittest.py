#!/usr/bin/python

import unittest, StringIO

import common
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.test_utils import mock


class test_read_one_line(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")


    def tearDown(self):
        self.god.unstub_all()


    def create_test_file(self, contents):
        test_file = StringIO.StringIO(contents)
        utils.open.expect_call("filename", "r").and_return(test_file)


    def test_reads_one_line_file(self):
        self.create_test_file("abc\n")
        self.assertEqual("abc", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_strips_read_lines(self):
        self.create_test_file("abc   \n")
        self.assertEqual("abc   ", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_drops_extra_lines(self):
        self.create_test_file("line 1\nline 2\nline 3\n")
        self.assertEqual("line 1", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_works_on_empty_file(self):
        self.create_test_file("")
        self.assertEqual("", utils.read_one_line("filename"))
        self.god.check_playback()


    def test_works_on_file_with_no_newlines(self):
        self.create_test_file("line but no newline")
        self.assertEqual("line but no newline",
                         utils.read_one_line("filename"))
        self.god.check_playback()


    def test_preserves_leading_whitespace(self):
        self.create_test_file("   has leading whitespace")
        self.assertEqual("   has leading whitespace",
                         utils.read_one_line("filename"))


class test_write_one_line(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(utils, "open")


    def tearDown(self):
        self.god.unstub_all()


    def get_write_one_line_output(self, content):
        test_file = StringIO.StringIO(content)
        utils.open.expect_call("filename", "w").and_return(test_file)
        utils.write_one_line("filename", content)
        self.god.check_playback()
        return test_file.getvalue()


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


if __name__ == "__main__":
    unittest.main()
