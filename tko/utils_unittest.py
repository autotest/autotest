#!/usr/bin/python

import os, unittest, time, datetime, itertools

import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.tko import utils


class get_timestamp_test(unittest.TestCase):
    def test_zero_time(self):
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


    def test_returns_none_on_missing_value(self):
        date = utils.get_timestamp({}, "missing_key")
        self.assertEquals(date, None)


    def test_fails_on_non_integer_values(self):
        self.assertRaises(ValueError, utils.get_timestamp,
                          {"key": "zero"}, "key")


    def test_date_can_be_string_or_integer(self):
        int_times = [1, 12, 123, 1234, 12345, 123456]
        str_times = [str(t) for t in int_times]
        for int_t, str_t in itertools.izip(int_times, str_times):
            date_int = utils.get_timestamp({"key": int_t}, "key")
            date_str = utils.get_timestamp({"key": str_t}, "key")
            self.assertEquals(date_int, date_str)


class find_toplevel_job_dir_test(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(os.path, "exists")


    def tearDown(self):
        self.god.unstub_all()


    def test_start_is_toplevel(self):
        jobdir = "/results/job1"
        os.path.exists.expect_call(
            jobdir + "/.autoserv_execute").and_return(True)
        self.assertEqual(utils.find_toplevel_job_dir(jobdir), jobdir)


    def test_parent_is_toplevel(self):
        jobdir = "/results/job2"
        os.path.exists.expect_call(
            jobdir + "/sub/.autoserv_execute").and_return(False)
        os.path.exists.expect_call(
            jobdir + "/.autoserv_execute").and_return(True)
        self.assertEqual(utils.find_toplevel_job_dir(jobdir + "/sub"), jobdir)


    def test_grandparent_is_toplevel(self):
        jobdir = "/results/job3"
        os.path.exists.expect_call(
            jobdir + "/sub/sub/.autoserv_execute").and_return(False)
        os.path.exists.expect_call(
            jobdir + "/sub/.autoserv_execute").and_return(False)
        os.path.exists.expect_call(
            jobdir + "/.autoserv_execute").and_return(True)
        self.assertEqual(utils.find_toplevel_job_dir(jobdir + "/sub/sub"),
                         jobdir)

    def test_root_is_toplevel(self):
        jobdir = "/results/job4"
        os.path.exists.expect_call(
            jobdir + "/.autoserv_execute").and_return(False)
        os.path.exists.expect_call(
            "/results/.autoserv_execute").and_return(False)
        os.path.exists.expect_call("/.autoserv_execute").and_return(True)
        self.assertEqual(utils.find_toplevel_job_dir(jobdir), "/")


    def test_no_toplevel(self):
        jobdir = "/results/job5"
        os.path.exists.expect_call(
            jobdir + "/.autoserv_execute").and_return(False)
        os.path.exists.expect_call(
            "/results/.autoserv_execute").and_return(False)
        os.path.exists.expect_call("/.autoserv_execute").and_return(False)
        self.assertEqual(utils.find_toplevel_job_dir(jobdir), None)


class drop_redundant_messages(unittest.TestCase):
    def test_empty_set(self):
        self.assertEqual(utils.drop_redundant_messages(set()), set())


    def test_singleton(self):
        self.assertEqual(utils.drop_redundant_messages(set(["abc"])),
                         set(["abc"]))


    def test_distinct_messages(self):
        self.assertEqual(utils.drop_redundant_messages(set(["abc", "def"])),
                         set(["abc", "def"]))


    def test_one_unique_message(self):
        self.assertEqual(
                utils.drop_redundant_messages(set(["abc", "abcd", "abcde"])),
                set(["abcde"]))


    def test_some_unique_some_not(self):
        self.assertEqual(
                utils.drop_redundant_messages(set(["abc", "def", "abcdef",
                                                   "defghi", "cd"])),
                set(["abcdef", "defghi"]))


if __name__ == "__main__":
    unittest.main()
