#!/usr/bin/python

import unittest

import common
from autotest_lib.tko.parsers import version_0


class test_status_line(unittest.TestCase):
	statuses = ["GOOD", "WARN", "FAIL", "ABORT"]


	def testHandlesSTART(self):
		line = version_0.status_line(0, "START", "----", "test",
					     "", {})
		self.assertEquals(line.type, "START")
		self.assertEquals(line.status, None)


	def testHandlesSTATUS(self):
		for stat in self.statuses:
			line = version_0.status_line(0, stat, "----", "test",
						     "", {})
			self.assertEquals(line.type, "STATUS")
			self.assertEquals(line.status, stat)


	def testHandlesENDSTATUS(self):
		for stat in self.statuses:
			line = version_0.status_line(0, "END " + stat, "----",
						     "test", "", {})
			self.assertEquals(line.type, "END")
			self.assertEquals(line.status, stat)


	def testFailsOnBadStatus(self):
		for stat in self.statuses:
			self.assertRaises(AssertionError,
					  version_0.status_line, 0,
					  "BAD " + stat, "----", "test",
					  "", {})


	def testSavesAllFields(self):
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


	def testParsesBlankSubdir(self):
		line = version_0.status_line(0, "GOOD", "----", "test",
					     "", {})
		self.assertEquals(line.subdir, None)


	def testParsesBlankTestname(self):
		line = version_0.status_line(0, "GOOD", "subdir", "----",
					     "", {})
		self.assertEquals(line.testname, None)


	def testParseLineSmoketest(self):
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

	def testParseLineHandlesNewline(self):
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


	def testParseLineFailsOnUntabbedLines(self):
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


	def testParseLineFailsOnBadOptionalFields(self):
		input_data = "GOOD\tfield1\tfield2\tfield3\tfield4"
		self.assertRaises(AssertionError,
				  version_0.status_line.parse_line,
				  input_data)


if __name__ == "__main__":
	unittest.main()
