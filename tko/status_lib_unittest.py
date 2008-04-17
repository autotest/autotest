#!/usr/bin/python

import unittest

import common
from autotest_lib.tko import status_lib


class line_buffer_test(unittest.TestCase):
	def testGetEmpty(self):
		buf = status_lib.line_buffer()
		self.assertRaises(IndexError, buf.get)


	def testGetSingle(self):
		buf = status_lib.line_buffer()
		buf.put("single line")
		self.assertEquals(buf.get(), "single line")
		self.assertRaises(IndexError, buf.get)


	def testIsFIFO(self):
		buf = status_lib.line_buffer()
		lines = ["line #%d" for x in xrange(10)]
		for line in lines:
			buf.put(line)
		results = []
		while buf.size():
			results.append(buf.get())
		self.assertEquals(lines, results)


	def testPutBackIsLIFO(self):
		buf = status_lib.line_buffer()
		lines = ["1", "2", "3"]
		for line in lines:
			buf.put(line)
		results = []
		results.append(buf.get())
		buf.put_back("1")
		buf.put_back("0")
		while buf.size():
			results.append(buf.get())
		self.assertEquals(results, ["1", "0", "1", "2", "3"])


	def testSizeIncreasedByPut(self):
		buf = status_lib.line_buffer()
		self.assertEquals(buf.size(), 0)
		buf.put("1")
		buf.put("2")
		self.assertEquals(buf.size(), 2)
		buf.put("3")
		self.assertEquals(buf.size(), 3)


	def testSizeIncreasedByPut(self):
		buf = status_lib.line_buffer()
		self.assertEquals(buf.size(), 0)
		buf.put("1")
		buf.put("2")
		self.assertEquals(buf.size(), 2)
		buf.put("3")
		self.assertEquals(buf.size(), 3)


	def testSizeDecreasedByGet(self):
		buf = status_lib.line_buffer()
		buf.put("1")
		buf.put("2")
		buf.put("3")
		self.assertEquals(buf.size(), 3)
		buf.get()
		self.assertEquals(buf.size(), 2)
		buf.get()
		buf.get()
		self.assertEquals(buf.size(), 0)


class status_stack_test(unittest.TestCase):
	def testDefaultToNOSTATUS(self):
		stack = status_lib.status_stack()
		self.assertEquals(stack.current_status(), "NOSTATUS")


	def testDefaultOnStartToNOSTATUS(self):
		stack = status_lib.status_stack()
		stack.update("FAIL")
		stack.start()
		self.assertEquals(stack.current_status(), "NOSTATUS")


	def testSizeAlwaysAtLeastZero(self):
		stack = status_lib.status_stack()
		self.assertEquals(stack.size(), 0)
		stack.start()
		stack.end()
		self.assertEquals(stack.size(), 0)
		stack.end()
		self.assertEquals(stack.size(), 0)


	def testAnythingOverridesNostatus(self):
		statuses = ["ABORT", "ERROR", "FAIL", "WARN", "GOOD"]
		for status in statuses:
			stack = status_lib.status_stack()
			stack.update(status)
			self.assertEquals(stack.current_status(), status)


	def testWorseOverridesBetter(self):
		statuses = ["ABORT", "ERROR", "FAIL", "WARN", "GOOD"]
		for i in xrange(len(statuses)):
			worse_status = statuses[i]
			for j in xrange(i + 1, len(statuses)):
				stack = status_lib.status_stack()
				better_status = statuses[j]
				stack.update(better_status)
				stack.update(worse_status)
				self.assertEquals(stack.current_status(),
						  worse_status)


	def testBetterNeverOverridesBetter(self):
		statuses = ["ABORT", "ERROR", "FAIL", "WARN", "GOOD"]
		for i in xrange(len(statuses)):
			better_status = statuses[i]
			for j in xrange(i):
				stack = status_lib.status_stack()
				worse_status = statuses[j]
				stack.update(worse_status)
				stack.update(better_status)
				self.assertEquals(stack.current_status(),
						  worse_status)


	def testStackIsLIFO(self):
		stack = status_lib.status_stack()
		stack.update("GOOD")
		stack.start()
		stack.update("FAIL")
		stack.start()
		stack.update("WARN")
		self.assertEquals(stack.end(), "WARN")
		self.assertEquals(stack.end(), "FAIL")
		self.assertEquals(stack.end(), "GOOD")
		self.assertEquals(stack.end(), "NOSTATUS")


class parser_test(unittest.TestCase):
	available_versions = [0]
	def testCanImportAvailableVersions(self):
		for version in self.available_versions:
			p = status_lib.parser(0)
			self.assertNotEqual(p, None)


if __name__ == "__main__":
	unittest.main()
