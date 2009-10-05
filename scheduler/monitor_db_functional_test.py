#!/usr/bin/python

import logging, unittest
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.database import database_connection
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.scheduler import drone_manager, email_manager, monitor_db

# translations necessary for scheduler queries to work with SQLite
_re_translator = database_connection.TranslatingDatabase.make_regexp_translator
_DB_TRANSLATORS = (
        _re_translator(r'NOW\(\)', 'time("now")'),
        # older SQLite doesn't support group_concat, so just don't bother until
        # it arises in an important query
        _re_translator(r'GROUP_CONCAT\((.*?)\)', r'\1'),
)

class NullMethodObject(object):
    _NULL_METHODS = ()

    def __init__(self):
        def null_method(*args, **kwargs):
            pass

        for method_name in self._NULL_METHODS:
            setattr(self, method_name, null_method)

class MockGlobalConfig(object):
    def __init__(self):
        self._config_info = {}


    def set_config_value(self, section, key, value):
        self._config_info[(section, key)] = value


    def get_config_value(self, section, key, type=str,
                         default=None, allow_blank=False):
        identifier = (section, key)
        if identifier not in self._config_info:
            raise RuntimeError('Unset global config value: %s' % (identifier,))
        return self._config_info[identifier]


class MockDroneManager(NullMethodObject):
    _NULL_METHODS = ('refresh', 'reinitialize_drones',
                     'copy_to_results_repository')

    def __init__(self):
        super(MockDroneManager, self).__init__()
        # maps result_dir to set of tuples (file_path, file_contents)
        self._attached_files = {}
        # maps pidfile IDs to PidfileContents
        self._pidfiles = {}
        # pidfile IDs that haven't been created yet
        self._future_pidfiles = []
        # the most recently created pidfile ID
        self._last_pidfile_id = None
        # maps (working_directory, pidfile_name) to pidfile IDs
        self._pidfile_index = {}


    # utility APIs for use by the test

    def set_last_pidfile_exit_status(self, exit_status):
        assert self._last_pidfile_id is not None
        self._set_pidfile_exit_status(self._last_pidfile_id, exit_status)


    def set_pidfile_exit_status(self, working_directory, pidfile_name,
                                exit_status):
        key = (working_directory, pidfile_name)
        self._set_pidfile_exit_status(self._pidfile_index[key], exit_status)

    def _set_pidfile_exit_status(self, pidfile_id, exit_status):
        contents = self._pidfiles[pidfile_id]
        contents.exit_status = exit_status
        contents.num_tests_failed = 0


    # DroneManager emulation APIs for use by monitor_db

    def get_orphaned_autoserv_processes(self):
        return set()


    def total_running_processes(self):
        return 0


    def max_runnable_processes(self):
        return 100


    def execute_actions(self):
        # executing an "execute_command" causes a pidfile to be created
        for pidfile_id in self._future_pidfiles:
            # Process objects are opaque to monitor_db
            self._pidfiles[pidfile_id].process = object()
        self._future_pidfiles = []


    def attach_file_to_execution(self, result_dir, file_contents,
                                 file_path=None):
        self._attached_files.setdefault(result_dir, set()).add((file_path,
                                                                file_contents))
        return 'attach_path'


    def execute_command(self, command, working_directory, pidfile_name,
                        log_file=None, paired_with_pidfile=None):
        # TODO: record this
        pidfile_id = object() # PidfileIds are opaque to monitor_db
        self._future_pidfiles.append(pidfile_id)
        self._pidfiles[pidfile_id] = drone_manager.PidfileContents()
        self._pidfile_index[(working_directory, pidfile_name)] = pidfile_id
        self._last_pidfile_id = pidfile_id
        return pidfile_id


    def get_pidfile_contents(self, pidfile_id, use_second_read=False):
        return self._pidfiles.get(pidfile_id,
                                           drone_manager.PidfileContents())


    def is_process_running(self, process):
        return True


    def register_pidfile(self, pidfile_id):
        # TODO
        pass


    def absolute_path(self, path):
        return 'absolute/' + path


    def write_lines_to_file(self, file_path, lines, paired_with_process=None):
        # TODO: record this
        pass


    def get_pidfile_id_from(self, execution_tag, pidfile_name):
        return self._pidfile_index.get((execution_tag, pidfile_name), object())


class MockEmailManager(NullMethodObject):
    _NULL_METHODS = ('send_queued_emails', 'send_email')


class SchedulerFunctionalTest(unittest.TestCase,
                              frontend_test_utils.FrontendTestMixin):
    # some number of ticks after which the scheduler is presumed to have
    # stabilized, given no external changes
    _A_LOT_OF_TICKS = 10

    def setUp(self):
        self._frontend_common_setup()
        self._set_stubs()
        self._set_global_config_values()
        self.dispatcher = monitor_db.Dispatcher()

        logging.basicConfig(level=logging.DEBUG)


    def tearDown(self):
        self._frontend_common_teardown()


    def _set_stubs(self):
        self.mock_config = MockGlobalConfig()
        self.god.stub_with(global_config, 'global_config', self.mock_config)

        self.mock_drone_manager = MockDroneManager()
        self.god.stub_with(monitor_db, '_drone_manager',
                           self.mock_drone_manager)

        self.mock_email_manager = MockEmailManager()
        self.god.stub_with(email_manager, 'manager', self.mock_email_manager)

        self._database = (
            database_connection.TranslatingDatabase.get_test_database(
                file_path=self._test_db_file,
                translators=_DB_TRANSLATORS))
        self._database.connect(db_type='django')
        self.god.stub_with(monitor_db, '_db', self._database)


    def _set_global_config_values(self):
        self.mock_config.set_config_value('SCHEDULER', 'pidfile_timeout_mins',
                                          1)


    def _initialize_test(self):
        self.dispatcher.initialize()


    def _run_dispatcher(self):
        for _ in xrange(self._A_LOT_OF_TICKS):
            self.dispatcher.tick()


    def test_idle(self):
        self._initialize_test()
        self._run_dispatcher()


    def test_simple_job(self):
        self._initialize_test()
        self._create_job(hosts=[1])
        self._run_dispatcher() # launches verify
        self.mock_drone_manager.set_last_pidfile_exit_status(0)
        self._run_dispatcher() # launches job
        self.mock_drone_manager.set_last_pidfile_exit_status(0)
        self._run_dispatcher() # launches parsing + cleanup
        self.mock_drone_manager.set_pidfile_exit_status(
                'hosts/host1/2-cleanup', monitor_db._AUTOSERV_PID_FILE, 0)
        self.mock_drone_manager.set_pidfile_exit_status(
                '1-my_user/host1', monitor_db._PARSER_PID_FILE, 0)
        self._run_dispatcher()


if __name__ == '__main__':
    unittest.main()
