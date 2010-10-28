#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for cli."""

import unittest, os, sys, StringIO

import common
from autotest_lib.cli import atest, topic_common, rpc
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.common_lib import autotemp

CLI_USING_PDB = False
CLI_UT_DEBUG = False

def create_file(content):
    file_temp = autotemp.tempfile(unique_id='cli_mock', text=True)
    os.write(file_temp.fd, content)
    return file_temp


class ExitException(Exception):
    pass


class cli_unittest(unittest.TestCase):
    def setUp(self):
        super(cli_unittest, self).setUp()
        self.god = mock.mock_god(debug=CLI_UT_DEBUG, ut=self)
        self.god.stub_class_method(rpc.afe_comm, 'run')
        self.god.stub_function(sys, 'exit')

        def stub_authorization_headers(*args, **kwargs):
            return {}
        self.god.stub_with(rpc_client_lib, 'authorization_headers',
                           stub_authorization_headers)


    def tearDown(self):
        super(cli_unittest, self).tearDown()
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


    def assertOutput(self, obj, results,
                     out_words_ok=[], out_words_no=[],
                     err_words_ok=[], err_words_no=[]):
        self.god.mock_io()
        obj.output(results)
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

        if not (CLI_USING_PDB and CLI_UT_DEBUG):
            self.god.mock_io()
        if exit_code is not None:
            sys.exit.expect_call(exit_code).and_raises(ExitException)
            self.assertRaises(ExitException, atest.main)
        else:
            atest.main()
        (out, err) = self.god.unmock_io()
        self.god.check_playback()
        self._check_output(out, out_words_ok, out_words_no,
                           err, err_words_ok, err_words_no)
        return (out, err)
