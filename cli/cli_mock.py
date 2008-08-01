#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for cli."""

import unittest, os, sys, tempfile, StringIO

import common
from autotest_lib.cli import atest, topic_common, rpc
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.client.common_lib.test_utils import mock

CLI_UT_DEBUG = False

def create_file(content):
    (fp, filename) = tempfile.mkstemp(text=True)
    os.write(fp, content)
    os.close(fp)
    return filename


class ExitException(Exception):
    pass


class cli_unittest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god(debug=CLI_UT_DEBUG)
        self.god.stub_class_method(rpc.afe_comm, 'run')
        self.god.stub_function(sys, 'exit')


    def tearDown(self):
        self.god.unstub_all()


    def assertEqualNoOrder(self, x, y, message=None):
        self.assertEqual(set(x), set(y), message)


    def assertWords(self, string, to_find=[], not_in=[]):
        for word in to_find:
            self.assert_(string.find(word) >= 0,
                         "Could not find '%s' in: %s" % (word, string))
        for word in not_in:
            self.assert_(string.find(word) < 0,
                         "Found (and shouldn't have) '%s' in: %s" % (word,
                                                                     string))


    def _check_output(self, out='', out_words_ok=[], out_words_no=[],
                      err='', err_words_ok=[], err_words_no=[]):
        if out_words_ok or out_words_no:
            self.assertWords(out, out_words_ok, out_words_no)
        else:
            self.assertEqual('', out)

        if err_words_ok or err_words_no:
            self.assertWords(err, err_words_ok, err_words_no)
        else:
            self.assertEqual('', err)


    def assertOutput(self, obj,
                     out_words_ok=[], out_words_no=[],
                     err_words_ok=[], err_words_no=[]):
        self.god.mock_io()
        obj.show_all_failures()
        (out, err) = self.god.unmock_io()
        self._check_output(out, out_words_ok, out_words_no,
                           err, err_words_ok, err_words_no)


    def mock_rpcs(self, rpcs):
        """rpcs is a list of tuples, each representing one RPC:
        (op, **dargs, success, expected)"""
        for (op, dargs, success, expected) in rpcs:
            comm = rpc.afe_comm.run
            if success:
                comm.expect_call(op, **dargs).and_return(expected)
            else:
                comm.expect_call(op, **dargs).and_raises(proxy.JSONRPCException(expected))



    def run_cmd(self, argv, rpcs=[], exit_code=None,
                out_words_ok=[], out_words_no=[],
                err_words_ok=[], err_words_no=[]):
        """Runs the command in argv.
        rpcs is a list of tuples, each representing one RPC:
             (op, **dargs, success, expected)
        exit_code should be set if you expect the command
        to fail
        The words are lists of words that are expected"""
        sys.argv = argv

        self.mock_rpcs(rpcs)

        if not CLI_UT_DEBUG:
            self.god.mock_io()
        if exit_code != None:
            sys.exit.expect_call(exit_code).and_raises(ExitException)
            self.assertRaises(ExitException, atest.main)
        else:
            atest.main()
        (out, err) = self.god.unmock_io()
        self.god.check_playback()
        self._check_output(out, out_words_ok, out_words_no,
                           err, err_words_ok, err_words_no)
        return (out, err)
