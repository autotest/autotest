from autotest.client.shared.test_utils import unittest
from autotest.database_legacy import database_connection
from autotest.frontend import test_utils
from autotest.scheduler import monitor_db, scheduler_models
from autotest.scheduler import drone_manager

class BaseSchedulerTest(unittest.TestCase,
                        test_utils.FrontendTestMixin):

    def _do_query(self, sql):
        self._database.execute(sql)

    def _set_monitor_stubs(self):
        # Clear the instance cache as this is a brand new database.
        scheduler_models.DBObject._clear_instance_cache()

        self._database = (
            database_connection.DatabaseConnection('AUTOTEST_WEB'))
        self._database.connect(db_type='django',
                               db_name='autotest_web_unittest_run')

        self.god.stub_with(monitor_db, '_db', self._database)
        self.god.stub_with(scheduler_models, '_db', self._database)
        self.god.stub_with(drone_manager.instance(), '_results_dir',
                           '/test/path')
        self.god.stub_with(drone_manager.instance(), '_temporary_directory',
                           '/test/path/tmp')

        monitor_db.initialize_globals()
        scheduler_models.initialize_globals()

    def setUp(self):
        self._frontend_common_setup()
        self._set_monitor_stubs()
        self._dispatcher = monitor_db.Dispatcher()

    def tearDown(self):
        self._database.disconnect()
        self._frontend_common_teardown()

    def _update_hqe(self, set, where=''):
        query = 'UPDATE afe_host_queue_entries SET ' + set
        if where:
            query += ' WHERE ' + where
        self._do_query(query)


