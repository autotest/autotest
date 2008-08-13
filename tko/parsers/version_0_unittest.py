#!/usr/bin/python

import unittest

import common
from autotest_lib.tko.parsers import version_0


class test_status_line(unittest.TestCase):
    statuses = ["GOOD", "WARN", "FAIL", "ABORT"]


    def test_handles_start(self):
        line = version_0.status_line(0, "START", "----", "test",
                                     "", {})
        self.assertEquals(line.type, "START")
        self.assertEquals(line.status, None)


    def test_handles_status(self):
        for stat in self.statuses:
            line = version_0.status_line(0, stat, "----", "test",
                                         "", {})
            self.assertEquals(line.type, "STATUS")
            self.assertEquals(line.status, stat)


    def test_handles_endstatus(self):
        for stat in self.statuses:
            line = version_0.status_line(0, "END " + stat, "----",
                                         "test", "", {})
            self.assertEquals(line.type, "END")
            self.assertEquals(line.status, stat)


    def test_fails_on_bad_status(self):
        for stat in self.statuses:
            self.assertRaises(AssertionError,
                              version_0.status_line, 0,
                              "BAD " + stat, "----", "test",
                              "", {})


    def test_saves_all_fields(self):
        line = version_0.status_line(5, "GOOD", "subdir_name",
                                     "test_name", "my reason here",
                                     {"key1": "value",
                                      "key2": "another value",
                                      "key3": "value3"})
        self.assertEquals(line.indent, 5)
        self.assertEquals(line.status, "GOOD")
        self.assertEquals(line.subdir, "subdir_name")
        self.assertEquals(line.testname, "test_name")
        self.assertEquals(line.reason, "my reason here")
        self.assertEquals(line.optional_fields,
                          {"key1": "value", "key2": "another value",
                           "key3": "value3"})


    def test_parses_blank_subdir(self):
        line = version_0.status_line(0, "GOOD", "----", "test",
                                     "", {})
        self.assertEquals(line.subdir, None)


    def test_parses_blank_testname(self):
        line = version_0.status_line(0, "GOOD", "subdir", "----",
                                     "", {})
        self.assertEquals(line.testname, None)


    def test_parse_line_smoketest(self):
        input_data = ("\t\t\tGOOD\t----\t----\t"
                      "field1=val1\tfield2=val2\tTest Passed")
        line = version_0.status_line.parse_line(input_data)
        self.assertEquals(line.indent, 3)
        self.assertEquals(line.type, "STATUS")
        self.assertEquals(line.status, "GOOD")
        self.assertEquals(line.subdir, None)
        self.assertEquals(line.testname, None)
        self.assertEquals(line.reason, "Test Passed")
        self.assertEquals(line.optional_fields,
                          {"field1": "val1", "field2": "val2"})

    def test_parse_line_handles_newline(self):
        input_data = ("\t\tGOOD\t----\t----\t"
                      "field1=val1\tfield2=val2\tNo newline here!")
        for suffix in ("", "\n"):
            line = version_0.status_line.parse_line(input_data +
                                                    suffix)
            self.assertEquals(line.indent, 2)
            self.assertEquals(line.type, "STATUS")
            self.assertEquals(line.status, "GOOD")
            self.assertEquals(line.subdir, None)
            self.assertEquals(line.testname, None)
            self.assertEquals(line.reason, "No newline here!")
            self.assertEquals(line.optional_fields,
                              {"field1": "val1",
                               "field2": "val2"})


    def test_parse_line_fails_on_untabbed_lines(self):
        input_data = "   GOOD\trandom\tfields\tof text"
        line = version_0.status_line.parse_line(input_data)
        self.assertEquals(line, None)
        line = version_0.status_line.parse_line(input_data.lstrip())
        self.assertEquals(line.indent, 0)
        self.assertEquals(line.type, "STATUS")
        self.assertEquals(line.status, "GOOD")
        self.assertEquals(line.subdir, "random")
        self.assertEquals(line.testname, "fields")
        self.assertEquals(line.reason, "of text")
        self.assertEquals(line.optional_fields, {})


    def test_parse_line_fails_on_incomplete_lines(self):
        input_data = "\t\tGOOD\tfield\tsecond field"
        complete_data = input_data + "\tneeded last field"
        line = version_0.status_line.parse_line(input_data)
        self.assertEquals(line, None)
        line = version_0.status_line.parse_line(complete_data)
        self.assertEquals(line.indent, 2)
        self.assertEquals(line.type, "STATUS")
        self.assertEquals(line.status, "GOOD")
        self.assertEquals(line.subdir, "field")
        self.assertEquals(line.testname, "second field")
        self.assertEquals(line.reason, "needed last field")
        self.assertEquals(line.optional_fields, {})


    def test_parse_line_fails_on_bad_optional_fields(self):
        input_data = "GOOD\tfield1\tfield2\tfield3\tfield4"
        self.assertRaises(AssertionError,
                          version_0.status_line.parse_line,
                          input_data)


if __name__ == "__main__":
    unittest.main()
