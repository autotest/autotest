#!/usr/bin/python

import unittest

import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.tko import models
from autotest_lib.tko.parsers import version_0


class test_job_load_from_dir(unittest.TestCase):
    keyval_return = {'job_queued': 1234567890,
                     'job_started': 1234567891,
                     'job_finished': 1234567892,
                     'user': 'janet',
                     'label': 'steeltown',
                     'hostname': 'abc123'}


    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(models.job, 'read_keyval')
        self.god.stub_function(version_0.job, 'find_hostname')
        self.god.stub_function(models.test, 'parse_host_keyval')


    def tearDown(self):
        self.god.unstub_all()


    def _expect_host_keyval(self, hostname, platform=None):
        return_dict = {}
        if platform:
            return_dict['platform'] = platform
            return_dict['labels'] = platform + ',other_label'
        (models.test.parse_host_keyval.expect_call('.', hostname)
                .and_return(return_dict))


    def test_load_from_dir_simple(self):
        models.job.read_keyval.expect_call('.').and_return(
                dict(self.keyval_return))
        self._expect_host_keyval('abc123', 'my_platform')
        job = version_0.job.load_from_dir('.')
        self.assertEqual('janet', job['user'])
        self.assertEqual('steeltown', job['label'])
        self.assertEqual('abc123', job['machine'])
        self.assertEqual('my_platform', job['machine_group'])
        self.god.check_playback()


    def _setup_two_machines(self):
        raw_keyval = dict(self.keyval_return)
        raw_keyval['hostname'] = 'easyas,abc123'
        models.job.read_keyval.expect_call('.').and_return(raw_keyval)


    def test_load_from_dir_two_machines(self):
        self._setup_two_machines()
        version_0.job.find_hostname.expect_call('.').and_raises(
                    version_0.NoHostnameError('find_hostname stubbed out'))
        self._expect_host_keyval('easyas', 'platform')
        self._expect_host_keyval('abc123', 'platform')

        job = version_0.job.load_from_dir('.')
        self.assertEqual('easyas,abc123', job['machine'])
        self.assertEqual('platform', job['machine_group'])

        self.god.check_playback()


    def test_load_from_dir_two_machines_with_find_hostname(self):
        self._setup_two_machines()
        version_0.job.find_hostname.expect_call('.').and_return('foo')
        self._expect_host_keyval('foo')

        job = version_0.job.load_from_dir('.')
        self.assertEqual('foo', job['machine'])

        self.god.check_playback()


    def test_load_from_dir_two_machines_different_platforms(self):
        self._setup_two_machines()
        version_0.job.find_hostname.expect_call('.').and_raises(
                    version_0.NoHostnameError('find_hostname stubbed out'))
        self._expect_host_keyval('easyas', 'platformZ')
        self._expect_host_keyval('abc123', 'platformA')

        job = version_0.job.load_from_dir('.')
        self.assertEqual('easyas,abc123', job['machine'])
        self.assertEqual('platformA,platformZ', job['machine_group'])

        self.god.check_playback()

    def test_load_from_dir_one_machine_group_name(self):
        raw_keyval = dict(self.keyval_return)
        raw_keyval['host_group_name'] = 'jackson five'
        models.job.read_keyval.expect_call('.').and_return(raw_keyval)
        self._expect_host_keyval('abc123')
        job = version_0.job.load_from_dir('.')
        self.assertEqual('janet', job['user'])
        self.assertEqual('abc123', job['machine'])
        self.god.check_playback()


    def test_load_from_dir_multi_machine_group_name(self):
        raw_keyval = dict(self.keyval_return)
        raw_keyval['user'] = 'michael'
        raw_keyval['hostname'] = 'abc123,dancingmachine'
        raw_keyval['host_group_name'] = 'jackson five'
        models.job.read_keyval.expect_call('.').and_return(raw_keyval)
        self._expect_host_keyval('jackson five')
        job = version_0.job.load_from_dir('.')
        self.assertEqual('michael', job['user'])
        # The host_group_name is used instead because machine appeared to be
        # a comma separated list.
        self.assertEqual('jackson five', job['machine'])
        self.god.check_playback()


    def test_load_from_dir_no_machine_group_name(self):
        raw_keyval = dict(self.keyval_return)
        del raw_keyval['hostname']
        raw_keyval['host_group_name'] = 'jackson five'
        models.job.read_keyval.expect_call('.').and_return(raw_keyval)
        self._expect_host_keyval('jackson five')
        job = version_0.job.load_from_dir('.')
        # The host_group_name is used because there is no machine.
        self.assertEqual('jackson five', job['machine'])
        self.god.check_playback()


class test_status_line(unittest.TestCase):
    statuses = ["GOOD", "WARN", "FAIL", "ABORT"]


    def test_handles_start(self):
        line = version_0.status_line(0, "START", "----", "test",
                                     "", {})
        self.assertEquals(line.type, "START")
        self.assertEquals(line.status, None)


    def test_fails_info(self):
        self.assertRaises(AssertionError,
                          version_0.status_line, 0, "INFO", "----", "----",
                          "", {})


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
