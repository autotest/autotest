#!/usr/bin/python

import logging, os, unittest
import common
from autotest_lib.client.common_lib import enum, global_config
from autotest_lib.database import database_connection
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils, models
from autotest_lib.scheduler import drone_manager, email_manager, monitor_db

# translations necessary for scheduler queries to work with SQLite
_re_translator = database_connection.TranslatingDatabase.make_regexp_translator
_DB_TRANSLATORS = (
        _re_translator(r'NOW\(\)', 'time("now")'),
        # older SQLite doesn't support group_concat, so just don't bother until
        # it arises in an important query
        _re_translator(r'GROUP_CONCAT\((.*?)\)', r'\1'),
)

HqeStatus = models.HostQueueEntry.Status
HostStatus = models.Host.Status

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


# the SpecialTask names here must match the suffixes used on the SpecialTask
# results directories
_PidfileType = enum.Enum('verify', 'cleanup', 'repair', 'job', 'gather',
                         'parse')


class MockDroneManager(NullMethodObject):
    _NULL_METHODS = ('reinitialize_drones', 'copy_to_results_repository',
                     'copy_results_on_drone')

    class _DummyPidfileId(object):
        """
        Object to represent pidfile IDs that is opaque to the scheduler code but
        still debugging-friendly for us.
        """
        def __init__(self, debug_string):
            self._debug_string = debug_string


        def __str__(self):
            return self._debug_string


    def __init__(self):
        super(MockDroneManager, self).__init__()
        # maps result_dir to set of tuples (file_path, file_contents)
        self._attached_files = {}
        # maps pidfile IDs to PidfileContents
        self._pidfiles = {}
        # pidfile IDs that haven't been created yet
        self._future_pidfiles = []
        # maps _PidfileType to the most recently created pidfile ID of that type
        self._last_pidfile_id = {}
        # maps (working_directory, pidfile_name) to pidfile IDs
        self._pidfile_index = {}
        # maps process to pidfile IDs
        self._process_index = {}
        # tracks pidfiles of processes that have been killed
        self._killed_pidfiles = set()
        # pidfile IDs that have just been unregistered (so will disappear on the
        # next cycle)
        self._unregistered_pidfiles = set()


    # utility APIs for use by the test

    def finish_process(self, pidfile_type, exit_status=0):
        pidfile_id = self._last_pidfile_id[pidfile_type]
        self._set_pidfile_exit_status(pidfile_id, exit_status)


    def _set_pidfile_exit_status(self, pidfile_id, exit_status):
        assert pidfile_id is not None
        contents = self._pidfiles[pidfile_id]
        contents.exit_status = exit_status
        contents.num_tests_failed = 0


    def was_last_process_killed(self, pidfile_type):
        pidfile_id = self._last_pidfile_id[pidfile_type]
        return pidfile_id in self._killed_pidfiles


    def running_pidfile_ids(self):
        return [str(pidfile_id) for pidfile_id, pidfile_contents
                in self._pidfiles.iteritems()
                if pidfile_contents.process is not None
                and pidfile_contents.exit_status is None]


    # DroneManager emulation APIs for use by monitor_db

    def get_orphaned_autoserv_processes(self):
        return set()


    def total_running_processes(self):
        return 0


    def max_runnable_processes(self):
        return 100


    def refresh(self):
        for pidfile_id in self._unregistered_pidfiles:
            # intentionally handle non-registered pidfiles silently
            self._pidfiles.pop(pidfile_id, None)
        self._unregistered_pidfiles = set()


    def execute_actions(self):
        # executing an "execute_command" causes a pidfile to be created
        for pidfile_id in self._future_pidfiles:
            # Process objects are opaque to monitor_db
            process = object()
            self._pidfiles[pidfile_id].process = process
            self._process_index[process] = pidfile_id
        self._future_pidfiles = []


    def attach_file_to_execution(self, result_dir, file_contents,
                                 file_path=None):
        self._attached_files.setdefault(result_dir, set()).add((file_path,
                                                                file_contents))
        return 'attach_path'


    def _initialize_pidfile(self, pidfile_id):
        if pidfile_id not in self._pidfiles:
            self._pidfiles[pidfile_id] = drone_manager.PidfileContents()


    _pidfile_type_map = {
            monitor_db._AUTOSERV_PID_FILE: _PidfileType.JOB,
            monitor_db._CRASHINFO_PID_FILE: _PidfileType.GATHER,
            monitor_db._PARSER_PID_FILE: _PidfileType.PARSE,
    }


    def _set_last_pidfile(self, pidfile_id, working_directory, pidfile_name):
        if working_directory.startswith('hosts/'):
            # such paths look like hosts/host1/1-verify, we'll grab the end
            type_string = working_directory.rsplit('-', 1)[1]
            pidfile_type = _PidfileType.get_value(type_string)
        else:
            pidfile_type = self._pidfile_type_map[pidfile_name]
        self._last_pidfile_id[pidfile_type] = pidfile_id


    def execute_command(self, command, working_directory, pidfile_name,
                        log_file=None, paired_with_pidfile=None):
        pidfile_id = self._DummyPidfileId(
                self._get_pidfile_debug_string(working_directory, pidfile_name))
        self._future_pidfiles.append(pidfile_id)
        self._initialize_pidfile(pidfile_id)
        self._pidfile_index[(working_directory, pidfile_name)] = pidfile_id
        self._set_last_pidfile(pidfile_id, working_directory, pidfile_name)
        return pidfile_id


    def _get_pidfile_debug_string(self, working_directory, pidfile_name):
        return os.path.join(working_directory, pidfile_name)


    def get_pidfile_contents(self, pidfile_id, use_second_read=False):
        if pidfile_id not in self._pidfiles:
            print 'Request for nonexistent pidfile %s' % pidfile_id
        return self._pidfiles.get(pidfile_id, drone_manager.PidfileContents())


    def is_process_running(self, process):
        return True


    def register_pidfile(self, pidfile_id):
        self._initialize_pidfile(pidfile_id)


    def unregister_pidfile(self, pidfile_id):
        self._unregistered_pidfiles.add(pidfile_id)


    def absolute_path(self, path):
        return 'absolute/' + path


    def write_lines_to_file(self, file_path, lines, paired_with_process=None):
        # TODO: record this
        pass


    def get_pidfile_id_from(self, execution_tag, pidfile_name):
        debug_string = ('Nonexistent pidfile: '
                        + self._get_pidfile_debug_string(execution_tag,
                                                         pidfile_name))
        return self._pidfile_index.get((execution_tag, pidfile_name),
                                       self._DummyPidfileId(debug_string))


    def kill_process(self, process):
        pidfile_id = self._process_index[process]
        self._killed_pidfiles.add(pidfile_id)
        self._set_pidfile_exit_status(pidfile_id, 271)


class MockEmailManager(NullMethodObject):
    _NULL_METHODS = ('send_queued_emails', 'send_email')

    def enqueue_notify_email(self, subject, message):
        logging.warn('enqueue_notify_email: %s', subject)
        logging.warn(message)


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


    def _assert_process_executed(self, working_directory, pidfile_name):
        process_was_executed = self.mock_drone_manager.was_process_executed(
                'hosts/host1/1-verify', monitor_db._AUTOSERV_PID_FILE)
        self.assert_(process_was_executed,
                     '%s/%s not executed' % (working_directory, pidfile_name))


    def _check_statuses(self, queue_entry, queue_entry_status, host_status):
        # update from DB
        queue_entry = models.HostQueueEntry.objects.get(id=queue_entry.id)
        self.assertEquals(queue_entry.status, queue_entry_status)
        self.assertEquals(queue_entry.host.status, host_status)


    def _run_pre_job_verify(self, queue_entry):
        self._run_dispatcher() # launches verify
        self._check_statuses(queue_entry, HqeStatus.VERIFYING,
                             HostStatus.VERIFYING)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)


    def test_simple_job(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        self._run_pre_job_verify(queue_entry)
        self._run_dispatcher() # launches job
        self._check_statuses(queue_entry, HqeStatus.RUNNING, HostStatus.RUNNING)
        self._finish_job(queue_entry)
        self._check_statuses(queue_entry, HqeStatus.COMPLETED, HostStatus.READY)
        self._assert_nothing_is_running()


    def _setup_for_pre_job_cleanup(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        job.reboot_before = models.RebootBefore.ALWAYS
        job.save()
        return queue_entry


    def _run_pre_job_cleanup_job(self, queue_entry):
        self._run_dispatcher() # cleanup
        self._check_statuses(queue_entry, HqeStatus.VERIFYING,
                             HostStatus.CLEANING)
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self._run_dispatcher() # verify
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher() # job
        self._finish_job(queue_entry)


    def test_pre_job_cleanup(self):
        queue_entry = self._setup_for_pre_job_cleanup()
        self._run_pre_job_cleanup_job(queue_entry)


    def _run_pre_job_cleanup_one_failure(self):
        queue_entry = self._setup_for_pre_job_cleanup()
        self._run_dispatcher() # cleanup
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher() # repair
        self._check_statuses(queue_entry, HqeStatus.QUEUED,
                             HostStatus.REPAIRING)
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR)
        return queue_entry


    def test_pre_job_cleanup_failure(self):
        queue_entry = self._run_pre_job_cleanup_one_failure()
        # from here the job should run as normal
        self._run_pre_job_cleanup_job(queue_entry)


    def test_pre_job_cleanup_double_failure(self):
        # TODO (showard): this test isn't perfect.  in reality, when the second
        # cleanup fails, it copies its results over to the job directory using
        # copy_results_on_drone() and then parses them.  since we don't handle
        # that, there appear to be no results at the job directory.  the
        # scheduler handles this gracefully, parsing gets effectively skipped,
        # and this test passes as is.  but we ought to properly test that
        # behavior.
        queue_entry = self._run_pre_job_cleanup_one_failure()
        self._run_dispatcher() # second cleanup
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.FAILED,
                             HostStatus.REPAIR_FAILED)
        # nothing else should run
        self._assert_nothing_is_running()


    def _assert_nothing_is_running(self):
        self.assertEquals(self.mock_drone_manager.running_pidfile_ids(), [])


    def _run_post_job_cleanup_failure_up_to_repair(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        job.reboot_after = models.RebootAfter.ALWAYS
        job.save()

        self._run_pre_job_verify(queue_entry)
        self._run_dispatcher() # job
        self.mock_drone_manager.finish_process(_PidfileType.JOB)
        self._run_dispatcher() # parsing + cleanup
        self.mock_drone_manager.finish_process(_PidfileType.PARSE)
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher() # repair, HQE unaffected
        self._check_statuses(queue_entry, HqeStatus.COMPLETED,
                             HostStatus.REPAIRING)
        return queue_entry


    def test_post_job_cleanup_failure(self):
        queue_entry = self._run_post_job_cleanup_failure_up_to_repair()
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.COMPLETED, HostStatus.READY)


    def test_post_job_cleanup_failure_repair_failure(self):
        queue_entry = self._run_post_job_cleanup_failure_up_to_repair()
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR,
                                               exit_status=256)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.COMPLETED,
                             HostStatus.REPAIR_FAILED)


    def _finish_job(self, queue_entry):
        self.mock_drone_manager.finish_process(_PidfileType.JOB)
        self._run_dispatcher() # launches parsing + cleanup
        self._check_statuses(queue_entry, HqeStatus.PARSING,
                             HostStatus.CLEANING)
        self._finish_parsing_and_cleanup()


    def _finish_parsing_and_cleanup(self):
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self.mock_drone_manager.finish_process(_PidfileType.PARSE)
        self._run_dispatcher()


    def test_job_abort_in_verify(self):
        self._initialize_test()
        job = self._create_job(hosts=[1])
        self._run_dispatcher() # launches verify
        job.hostqueueentry_set.update(aborted=True)
        self._run_dispatcher() # kills verify, launches cleanup
        self.assert_(self.mock_drone_manager.was_last_process_killed(
                _PidfileType.VERIFY))
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self._run_dispatcher()


    def test_job_abort(self):
        self._initialize_test()
        job = self._create_job(hosts=[1])
        job.run_verify = False
        job.save()

        self._run_dispatcher() # launches job
        job.hostqueueentry_set.update(aborted=True)
        self._run_dispatcher() # kills job, launches gathering
        self.assert_(self.mock_drone_manager.was_last_process_killed(
                _PidfileType.JOB))
        self.mock_drone_manager.finish_process(_PidfileType.GATHER)
        self._run_dispatcher() # launches parsing + cleanup
        self._finish_parsing_and_cleanup()


    def test_no_pidfile_leaking(self):
        self._initialize_test()
        self.test_simple_job()
        self.assertEquals(self.mock_drone_manager._pidfiles, {})

        self.test_job_abort_in_verify()
        self.assertEquals(self.mock_drone_manager._pidfiles, {})

        self.test_job_abort()
        self.assertEquals(self.mock_drone_manager._pidfiles, {})


    def _make_job_and_queue_entry(self):
        job = self._create_job(hosts=[1])
        queue_entry = job.hostqueueentry_set.all()[0]
        return job, queue_entry


    def test_recover_running_no_process(self):
        # recovery should re-execute a Running HQE if no process is found
        _, queue_entry = self._make_job_and_queue_entry()
        queue_entry.status = HqeStatus.RUNNING
        queue_entry.execution_subdir = '1-myuser/host1'
        queue_entry.save()
        queue_entry.host.status = HostStatus.RUNNING
        queue_entry.host.save()

        self._initialize_test()
        self._run_dispatcher()
        self._finish_job(queue_entry)


    def test_recover_verifying_hqe_no_special_task(self):
        # recovery should fail on a Verifing HQE with no corresponding
        # Verify or Cleanup SpecialTask
        _, queue_entry = self._make_job_and_queue_entry()
        queue_entry.status = HqeStatus.VERIFYING
        queue_entry.save()

        # make some dummy SpecialTasks that shouldn't count
        models.SpecialTask.objects.create(host=queue_entry.host,
                                          task=models.SpecialTask.Task.VERIFY)
        models.SpecialTask.objects.create(host=queue_entry.host,
                                          task=models.SpecialTask.Task.CLEANUP,
                                          queue_entry=queue_entry,
                                          is_complete=True)

        self.assertRaises(monitor_db.SchedulerError, self._initialize_test)


    def _test_recover_verifying_hqe_helper(self, task, pidfile_type):
        _, queue_entry = self._make_job_and_queue_entry()
        queue_entry.status = HqeStatus.VERIFYING
        queue_entry.save()

        special_task = models.SpecialTask.objects.create(
                host=queue_entry.host, task=task, queue_entry=queue_entry)

        self._initialize_test()
        self._run_dispatcher()
        self.mock_drone_manager.finish_process(pidfile_type)
        self._run_dispatcher()
        # don't bother checking the rest of the job execution, as long as the
        # SpecialTask ran


    def test_recover_verifying_hqe_with_cleanup(self):
        # recover an HQE that was in pre-job cleanup
        self._test_recover_verifying_hqe_helper(models.SpecialTask.Task.CLEANUP,
                                                _PidfileType.CLEANUP)


    def test_recover_verifying_hqe_with_verify(self):
        # recover an HQE that was in pre-job verify
        self._test_recover_verifying_hqe_helper(models.SpecialTask.Task.VERIFY,
                                                _PidfileType.VERIFY)


if __name__ == '__main__':
    unittest.main()
