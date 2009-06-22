#!/usr/bin/python

import unittest, time
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.database import database_connection

_CONFIG_SECTION = 'TKO'
_HOST = 'myhost'
_USER = 'myuser'
_PASS = 'mypass'
_DB_NAME = 'mydb'
_DB_TYPE = 'mydbtype'

_CONNECT_KWARGS = dict(host=_HOST, username=_USER, password=_PASS,
                       db_name=_DB_NAME)
_RECONNECT_DELAY = 10

class FakeDatabaseError(Exception):
    pass


class DatabaseConnectionTest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.stub_function(time, 'sleep')


    def tearDown(self):
        global_config.global_config.reset_config_values()
        self.god.unstub_all()


    def _get_database_connection(self, config_section=_CONFIG_SECTION):
        if config_section == _CONFIG_SECTION:
            self._override_config()
        db = database_connection.DatabaseConnection(config_section)

        self._fake_backend = self.god.create_mock_class(
            database_connection._GenericBackend, 'fake_backend')
        for exception in database_connection._DB_EXCEPTIONS:
            setattr(self._fake_backend, exception, FakeDatabaseError)
        self._fake_backend.rowcount = 0

        def get_fake_backend(db_type):
            self._db_type = db_type
            return self._fake_backend
        self.god.stub_with(db, '_get_backend', get_fake_backend)

        db.reconnect_delay_sec = _RECONNECT_DELAY
        return db


    def _override_config(self):
        c = global_config.global_config
        c.override_config_value(_CONFIG_SECTION, 'host', _HOST)
        c.override_config_value(_CONFIG_SECTION, 'user', _USER)
        c.override_config_value(_CONFIG_SECTION, 'password', _PASS)
        c.override_config_value(_CONFIG_SECTION, 'database', _DB_NAME)
        c.override_config_value(_CONFIG_SECTION, 'db_type', _DB_TYPE)


    def test_connect(self):
        db = self._get_database_connection(config_section=None)
        self._fake_backend.connect.expect_call(**_CONNECT_KWARGS)

        db.connect(db_type=_DB_TYPE, host=_HOST, username=_USER,
                   password=_PASS, db_name=_DB_NAME)

        self.assertEquals(self._db_type, _DB_TYPE)
        self.god.check_playback()


    def test_global_config(self):
        db = self._get_database_connection()
        self._fake_backend.connect.expect_call(**_CONNECT_KWARGS)

        db.connect()

        self.assertEquals(self._db_type, _DB_TYPE)
        self.god.check_playback()


    def _expect_reconnect(self, fail=False):
        self._fake_backend.disconnect.expect_call()
        call = self._fake_backend.connect.expect_call(**_CONNECT_KWARGS)
        if fail:
            call.and_raises(FakeDatabaseError())


    def _expect_fail_and_reconnect(self, num_reconnects, fail_last=False):
        self._fake_backend.connect.expect_call(**_CONNECT_KWARGS).and_raises(
            FakeDatabaseError())
        for i in xrange(num_reconnects):
            time.sleep.expect_call(_RECONNECT_DELAY)
            if i < num_reconnects - 1:
                self._expect_reconnect(fail=True)
            else:
                self._expect_reconnect(fail=fail_last)


    def test_connect_retry(self):
        db = self._get_database_connection()
        self._expect_fail_and_reconnect(1)

        db.connect()
        self.god.check_playback()

        self._fake_backend.disconnect.expect_call()
        self._expect_fail_and_reconnect(0)
        self.assertRaises(FakeDatabaseError, db.connect,
                          try_reconnecting=False)
        self.god.check_playback()

        db.reconnect_enabled = False
        self._fake_backend.disconnect.expect_call()
        self._expect_fail_and_reconnect(0)
        self.assertRaises(FakeDatabaseError, db.connect)
        self.god.check_playback()


    def test_max_reconnect(self):
        db = self._get_database_connection()
        db.max_reconnect_attempts = 5
        self._expect_fail_and_reconnect(5, fail_last=True)

        self.assertRaises(FakeDatabaseError, db.connect)
        self.god.check_playback()


    def test_reconnect_forever(self):
        db = self._get_database_connection()
        db.max_reconnect_attempts = database_connection.RECONNECT_FOREVER
        self._expect_fail_and_reconnect(30)

        db.connect()
        self.god.check_playback()


    def _simple_connect(self, db):
        self._fake_backend.connect.expect_call(**_CONNECT_KWARGS)
        db.connect()
        self.god.check_playback()


    def test_disconnect(self):
        db = self._get_database_connection()
        self._simple_connect(db)
        self._fake_backend.disconnect.expect_call()

        db.disconnect()
        self.god.check_playback()


    def test_execute(self):
        db = self._get_database_connection()
        self._simple_connect(db)
        params = object()
        self._fake_backend.execute.expect_call('query', params)

        db.execute('query', params)
        self.god.check_playback()


    def test_execute_retry(self):
        db = self._get_database_connection()
        self._simple_connect(db)
        self._fake_backend.execute.expect_call('query', None).and_raises(
            FakeDatabaseError())
        self._expect_reconnect()
        self._fake_backend.execute.expect_call('query', None)

        db.execute('query')
        self.god.check_playback()

        self._fake_backend.execute.expect_call('query', None).and_raises(
            FakeDatabaseError())
        self.assertRaises(FakeDatabaseError, db.execute, 'query',
                          try_reconnecting=False)


if __name__ == '__main__':
    unittest.main()
