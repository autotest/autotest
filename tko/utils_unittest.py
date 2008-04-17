#!/usr/bin/python

import unittest, time, datetime, itertools

import common
from autotest_lib.tko import utils


class get_timestamp_test(unittest.TestCase):
	def testZeroTime(self):
		date = utils.get_timestamp({"key": "0"}, "key")
		timezone = datetime.timedelta(seconds=time.timezone)
		utc_date = date + timezone
		# should be equal to epoch, i.e. Jan 1, 1970
		self.assertEquals(utc_date.year, 1970)
		self.assertEquals(utc_date.month, 1)
		self.assertEquals(utc_date.day, 1)
		self.assertEquals(utc_date.hour, 0)
		self.assertEquals(utc_date.minute, 0)
		self.assertEquals(utc_date.second, 0)
		self.assertEquals(utc_date.microsecond, 0)


	def testReturnsNoneOnMissingValue(self):
		date = utils.get_timestamp({}, "missing_key")
		self.assertEquals(date, None)


	def testFailsOnNonIntegerValues(self):
		self.assertRaises(ValueError, utils.get_timestamp,
				  {"key": "zero"}, "key")


	def testDateCanBeStringOrInteger(self):
		int_times = [1, 12, 123, 1234, 12345, 123456]
		str_times = [str(t) for t in int_times]
		for int_t, str_t in itertools.izip(int_times, str_times):
			date_int = utils.get_timestamp({"key": int_t}, "key")
			date_str = utils.get_timestamp({"key": str_t}, "key")
			self.assertEquals(date_int, date_str)


if __name__ == "__main__":
	unittest.main()
