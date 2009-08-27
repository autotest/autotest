#!/usr/bin/python

import unittest
import common
from autotest_lib.tko import status_lib
from autotest_lib.client.common_lib import log


class clean_raw_line_test(unittest.TestCase):
    def test_default(self):
        raw_line_temp = 'this \r is a %s line \x00 yeah\n'
        raw_line = raw_line_temp % status_lib.DEFAULT_BLACKLIST[0]
        cleaned = status_lib.clean_raw_line(raw_line)
        self.assertEquals(cleaned, raw_line_temp % '')


    def test_multi(self):
        blacklist = ('\r\x00', 'FOOBAR', 'BLAh')
        raw_line_temp = 'this \x00 FOO is BAR \r a %s line %s BL yeah %s ah\n'
        raw_line = raw_line_temp % blacklist
        cleaned = status_lib.clean_raw_line(raw_line, blacklist)
        self.assertEquals(
            cleaned, raw_line_temp % (('',) * len(blacklist)))


class line_buffer_test(unittest.TestCase):
    def test_get_empty(self):
        buf = status_lib.line_buffer()
        self.assertRaises(IndexError, buf.get)


    def test_get_single(self):
        buf = status_lib.line_buffer()
        buf.put("single line")
        self.assertEquals(buf.get(), "single line")
        self.assertRaises(IndexError, buf.get)


    def test_is_fifo(self):
        buf = status_lib.line_buffer()
        lines = ["line #%d" for x in xrange(10)]
        for line in lines:
            buf.put(line)
        results = []
        while buf.size():
            results.append(buf.get())
        self.assertEquals(lines, results)


    def test_put_multiple_same_as_multiple_puts(self):
        buf_put, buf_multi = [status_lib.line_buffer()
                              for x in xrange(2)]
        lines = ["line #%d" % x for x in xrange(10)]
        for line in lines:
            buf_put.put(line)
        buf_multi.put_multiple(lines)
        counter = 0
        while buf_put.size():
            self.assertEquals(buf_put.size(), buf_multi.size())
            line = "line #%d" % counter
            self.assertEquals(buf_put.get(), line)
            self.assertEquals(buf_multi.get(), line)
            counter += 1


    def test_put_back_is_lifo(self):
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


    def test_size_increased_by_put(self):
        buf = status_lib.line_buffer()
        self.assertEquals(buf.size(), 0)
        buf.put("1")
        buf.put("2")
        self.assertEquals(buf.size(), 2)
        buf.put("3")
        self.assertEquals(buf.size(), 3)


    def test_size_decreased_by_get(self):
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
    statuses = log.job_statuses

    def test_default_to_nostatus(self):
        stack = status_lib.status_stack()
        self.assertEquals(stack.current_status(), "NOSTATUS")


    def test_default_on_start_to_nostatus(self):
        stack = status_lib.status_stack()
        stack.update("FAIL")
        stack.start()
        self.assertEquals(stack.current_status(), "NOSTATUS")


    def test_size_always_at_least_zero(self):
        stack = status_lib.status_stack()
        self.assertEquals(stack.size(), 0)
        stack.start()
        stack.end()
        self.assertEquals(stack.size(), 0)
        stack.end()
        self.assertEquals(stack.size(), 0)


    def test_anything_overrides_nostatus(self):
        for status in self.statuses:
            stack = status_lib.status_stack()
            stack.update(status)
            self.assertEquals(stack.current_status(), status)


    def test_worse_overrides_better(self):
        for i in xrange(len(self.statuses)):
            worse_status = self.statuses[i]
            for j in xrange(i + 1, len(self.statuses)):
                stack = status_lib.status_stack()
                better_status = self.statuses[j]
                stack.update(better_status)
                stack.update(worse_status)
                self.assertEquals(stack.current_status(),
                                  worse_status)


    def test_better_never_overrides_better(self):
        for i in xrange(len(self.statuses)):
            better_status = self.statuses[i]
            for j in xrange(i):
                stack = status_lib.status_stack()
                worse_status = self.statuses[j]
                stack.update(worse_status)
                stack.update(better_status)
                self.assertEquals(stack.current_status(),
                                  worse_status)


    def test_stack_is_lifo(self):
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
    available_versions = [0, 1]
    def test_can_import_available_versions(self):
        for version in self.available_versions:
            p = status_lib.parser(0)
            self.assertNotEqual(p, None)


if __name__ == "__main__":
    unittest.main()
