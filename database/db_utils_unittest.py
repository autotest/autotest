#!/usr/bin/python

import unittest
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.database import migrate, db_utils

class UtilsTest(unittest.TestCase):

    EXISTS_QUERY_BASE = ('SELECT table_name FROM information_schema.%s '
                         'WHERE table_schema = %%s')
    DB_NAME = 'test_db'


    def setUp(self):
        self.god = mock.mock_god()
        self.manager = self.god.create_mock_class(migrate.MigrationManager,
                                                  'manager')

        self.god.stub_function(self.manager, 'execute')
        self.god.stub_function(self.manager, 'get_db_name')


    def tearDown(self):
        self.god.unstub_all()


    def test_check_exists(self):
        views = ('view1', 'view2')
        def _call_check_exists():
            db_utils.check_exists(self.manager, views, db_utils.VIEW_TYPE)

        self._setup_exists_expects(views, 'VIEWS')
        _call_check_exists()
        self.god.check_playback()

        self._setup_exists_expects(('view1',), 'VIEWS')
        self.assertRaises(Exception, _call_check_exists)
        self.god.check_playback()


    def test_drop_views(self):
        views = ('view1', 'view2')
        self._setup_exists_expects(views, 'VIEWS')

        for view in views:
            self.manager.execute.expect_call('DROP VIEW `%s`' % view)

        db_utils.drop_views(self.manager, views)
        self.god.check_playback()


    def test_rename(self):
        mapping = {
                'table1' : 'new_table1',
                'table2' : 'new_table2',
                }
        self._setup_exists_expects((name for name, _ in mapping.iteritems()),
                                   'TABLES')

        for name, new_name in mapping.iteritems():
            self.manager.execute.expect_call(
                    'RENAME TABLE `%s` TO `%s`' % (name, new_name))

        db_utils.rename(self.manager, mapping)
        self.god.check_playback()


    def _setup_exists_expects(self, names, table):
        self.manager.get_db_name.expect_call().and_return(self.DB_NAME)
        self.manager.execute.expect_call(
                self.EXISTS_QUERY_BASE % table, self.DB_NAME).and_return(
                self._create_exists_query_result(names))


    def _create_exists_query_result(self, names):
        return ((name, None) for name in names)


if __name__ == '__main__':
    unittest.main()
