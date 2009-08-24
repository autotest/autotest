#!/usr/bin/python
# Copyright 2009 Google Inc. Released under the GPL v2

import unittest

import common
from autotest_lib.mirror import database
from autotest_lib.client.common_lib.test_utils import mock

class dict_database_unittest(unittest.TestCase):
    _path = 'somepath.db'

    _db_contents = {
        'file1': database.item('file1', 10, 10000),
        'file2': database.item('file2', 20, 20000),
        }

    def setUp(self):
        self.god = mock.mock_god()

        self.god.stub_function(database.cPickle, 'load')
        self.god.stub_function(database.cPickle, 'dump')
        self.god.stub_function(database.tempfile, 'mkstemp')
        self.god.stub_function(database.os, 'fdopen')
        self.god.stub_function(database.os, 'close')
        self.god.stub_function(database.os, 'rename')
        self.god.stub_function(database.os, 'unlink')
        self._open_mock = self.god.create_mock_function('open')
        self._file_instance = self.god.create_mock_class(file, 'file')


    def tearDown(self):
        self.god.unstub_all()


    def test_get_dictionary_no_file(self):
        # record
        (self._open_mock.expect_call(self._path, 'rb')
            .and_raises(IOError('blah')))

        # playback
        db = database.dict_database(self._path)
        self.assertEqual(db.get_dictionary(_open_func=self._open_mock), {})

        self.god.check_playback()


    def test_get_dictionary(self):
        # record
        (self._open_mock.expect_call(self._path, 'rb')
            .and_return(self._file_instance))
        (database.cPickle.load.expect_call(self._file_instance)
            .and_return(self._db_contents))
        self._file_instance.close.expect_call()

        # playback
        db = database.dict_database(self._path)
        self.assertEqual(db.get_dictionary(_open_func=self._open_mock),
                         self._db_contents)

        self.god.check_playback()


    def _setup_merge_dictionary(self):
        # setup
        db = database.dict_database(self._path)
        self.god.stub_function(db, 'get_dictionary')
        self.god.stub_function(db, '_aquire_lock')

        new_files = {
            'file3': database.item('file3', 30, 30000),
            'file4': database.item('file4', 40, 40000),
            }
        all_files = dict(self._db_contents)
        all_files.update(new_files)

        # record
        db._aquire_lock.expect_call().and_return(3)
        db.get_dictionary.expect_call().and_return(self._db_contents)
        (database.tempfile.mkstemp.expect_call(prefix=self._path, dir='')
                .and_return((4, 'tmpfile')))
        database.os.fdopen.expect_call(4, 'wb').and_return(self._file_instance)

        return db, new_files, all_files


    def test_merge_dictionary(self):
        db, new_files, all_files = self._setup_merge_dictionary()

        database.cPickle.dump.expect_call(all_files, self._file_instance,
                protocol=database.cPickle.HIGHEST_PROTOCOL)
        self._file_instance.close.expect_call()
        database.os.rename.expect_call('tmpfile', self._path)
        database.os.close.expect_call(3)

        # playback
        db.merge_dictionary(new_files)
        self.god.check_playback()


    def test_merge_dictionary_disk_full(self):
        err = Exception('fail')
        db, new_files, all_files = self._setup_merge_dictionary()

        database.cPickle.dump.expect_call(all_files, self._file_instance,
                protocol=database.cPickle.HIGHEST_PROTOCOL).and_raises(err)
        self._file_instance.close.expect_call().and_raises(err)
        database.os.unlink.expect_call('tmpfile')
        database.os.close.expect_call(3)

        # playback
        self.assertRaises(Exception, db.merge_dictionary, new_files)
        self.god.check_playback()


if __name__ == '__main__':
    unittest.main()
