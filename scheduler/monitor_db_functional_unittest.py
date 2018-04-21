#!/usr/bin/python

import logging
import os
import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import enum, settings, host_protections, mail
from autotest.database_legacy import database_connection
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import test_utils
from autotest.frontend.afe import models
from autotest.frontend.afe import model_attributes
from autotest.scheduler import drone_manager, host_scheduler
from autotest.scheduler import monitor_db, scheduler_models

# translations necessary for scheduler queries to work with SQLite
_re_translator = database_connection.TranslatingDatabase.make_regexp_translator
_DB_TRANSLATORS = (
    _re_translator(r'NOW\(\)', 'time("now")'),
    _re_translator(r'LAST_INSERT_ID\(\)', 'LAST_INSERT_ROWID()'),
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

    def get_value(self, section, key, type=str,
                  default=None, allow_blank=False):
        identifier = (section, key)
        if identifier not in self._config_info:
            return default
        return self._config_info[identifier]


# the SpecialTask names here must match the suffixes used on the SpecialTask
# results directories
_PidfileType = enum.Enum('verify', 'cleanup', 'repair', 'job', 'gather',
                         'parse', 'archive')


_PIDFILE_TO_PIDFILE_TYPE = {
    drone_manager.AUTOSERV_PID_FILE: _PidfileType.JOB,
    drone_manager.CRASHINFO_PID_FILE: _PidfileType.GATHER,
    drone_manager.PARSER_PID_FILE: _PidfileType.PARSE,
    drone_manager.ARCHIVER_PID_FILE: _PidfileType.ARCHIVE,
}


_PIDFILE_TYPE_TO_PIDFILE = dict((value, key) for key, value
                                in _PIDFILE_TO_PIDFILE_TYPE.items())


class MockDroneManager(NullMethodObject):

    """
    Public attributes:
    max_runnable_processes_value: value returned by max_runnable_processes().
            tests can change this to activate throttling.
    """
    _NULL_METHODS = ('reinitialize_drones', 'copy_to_results_repository',
                     'copy_results_on_drone')

    class _DummyPidfileId(object):

        """
        Object to represent pidfile IDs that is opaque to the scheduler code but
        still debugging-friendly for us.
        """

        def __init__(self, working_directory, pidfile_name, num_processes=None):
            self._working_directory = working_directory
            self._pidfile_name = pidfile_name
            self._num_processes = num_processes
            self._paired_with_pidfile = None

        def key(self):
            """Key for MockDroneManager._pidfile_index"""
            return (self._working_directory, self._pidfile_name)

        def __str__(self):
            return os.path.join(self._working_directory, self._pidfile_name)

        def __repr__(self):
            return '<_DummyPidfileId: %s>' % str(self)

    def __init__(self):
        super(MockDroneManager, self).__init__()
        self.process_capacity = 100

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

    def finish_specific_process(self, working_directory, pidfile_name):
        pidfile_id = self.pidfile_from_path(working_directory, pidfile_name)
        self._set_pidfile_exit_status(pidfile_id, 0)

    def _set_pidfile_exit_status(self, pidfile_id, exit_status):
        assert pidfile_id is not None
        contents = self._pidfiles[pidfile_id]
        contents.exit_status = exit_status
        contents.num_tests_failed = 0

    def was_last_process_killed(self, pidfile_type):
        pidfile_id = self._last_pidfile_id[pidfile_type]
        return pidfile_id in self._killed_pidfiles

    def nonfinished_pidfile_ids(self):
        return [pidfile_id for pidfile_id, pidfile_contents
                in self._pidfiles.items()
                if pidfile_contents.exit_status is None]

    def running_pidfile_ids(self):
        return [pidfile_id for pidfile_id in self.nonfinished_pidfile_ids()
                if self._pidfiles[pidfile_id].process is not None]

    def pidfile_from_path(self, working_directory, pidfile_name):
        return self._pidfile_index[(working_directory, pidfile_name)]

    def attached_files(self, working_directory):
        """
        Return dict mapping path to contents for attached files with specified
        paths.
        """
        return dict((path, contents) for path, contents
                    in self._attached_files.get(working_directory, [])
                    if path is not None)

    # DroneManager emulation APIs for use by monitor_db
    def get_orphaned_autoserv_processes(self):
        return set()

    def total_running_processes(self):
        return sum(pidfile_id._num_processes
                   for pidfile_id in self.nonfinished_pidfile_ids())

    def max_runnable_processes(self, username, drone_hostnames_allowed):
        return self.process_capacity - self.total_running_processes()

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
            assert pidfile_id.key() not in self._pidfile_index
            self._pidfiles[pidfile_id] = drone_manager.PidfileContents()
            self._pidfile_index[pidfile_id.key()] = pidfile_id

    def _set_last_pidfile(self, pidfile_id, working_directory, pidfile_name):
        if working_directory.startswith('hosts/'):
            # such paths look like hosts/host1/1-verify, we'll grab the end
            type_string = working_directory.rsplit('-', 1)[1]
            pidfile_type = _PidfileType.get_value(type_string)
        else:
            pidfile_type = _PIDFILE_TO_PIDFILE_TYPE[pidfile_name]
        self._last_pidfile_id[pidfile_type] = pidfile_id

    def execute_command(self, command, working_directory, pidfile_name,
                        num_processes, log_file=None, paired_with_pidfile=None,
                        username=None, drone_hostnames_allowed=None):
        logging.debug('Executing %s in %s', command, working_directory)
        pidfile_id = self._DummyPidfileId(working_directory, pidfile_name)
        if pidfile_id.key() in self._pidfile_index:
            pidfile_id = self._pidfile_index[pidfile_id.key()]
        pidfile_id._num_processes = num_processes
        pidfile_id._paired_with_pidfile = paired_with_pidfile

        self._future_pidfiles.append(pidfile_id)
        self._initialize_pidfile(pidfile_id)
        self._pidfile_index[(working_directory, pidfile_name)] = pidfile_id
        self._set_last_pidfile(pidfile_id, working_directory, pidfile_name)
        return pidfile_id

    def get_pidfile_contents(self, pidfile_id, use_second_read=False):
        if pidfile_id not in self._pidfiles:
            logging.debug('Request for nonexistent pidfile %s' % pidfile_id)
        return self._pidfiles.get(pidfile_id, drone_manager.PidfileContents())

    def is_process_running(self, process):
        return True

    def register_pidfile(self, pidfile_id):
        self._initialize_pidfile(pidfile_id)

    def unregister_pidfile(self, pidfile_id):
        self._unregistered_pidfiles.add(pidfile_id)

    def declare_process_count(self, pidfile_id, num_processes):
        pidfile_id.num_processes = num_processes

    def absolute_path(self, path):
        return 'absolute/' + path

    def write_lines_to_file(self, file_path, lines, paired_with_process=None):
        # TODO: record this
        pass

    def get_pidfile_id_from(self, execution_tag, pidfile_name):
        default_pidfile = self._DummyPidfileId(execution_tag, pidfile_name,
                                               num_processes=0)
        return self._pidfile_index.get((execution_tag, pidfile_name),
                                       default_pidfile)

    def kill_process(self, process):
        pidfile_id = self._process_index[process]
        self._killed_pidfiles.add(pidfile_id)
        self._set_pidfile_exit_status(pidfile_id, 271)


class MockEmailManager(NullMethodObject):
    _NULL_METHODS = ('send_queued_admin', 'send')

    def enqueue_admin(self, subject, message):
        logging.warn('enqueue_notify_email: %s', subject)
        logging.warn(message)


class SchedulerFunctionalTest(unittest.TestCase,
                              test_utils.FrontendTestMixin):
    # some number of ticks after which the scheduler is presumed to have
    # stabilized, given no external changes
    _A_LOT_OF_TICKS = 10

    def setUp(self):
        self._frontend_common_setup()
        self._set_stubs()
        self._set_settings_values()
        self._create_dispatcher()

        logging.basicConfig(level=logging.DEBUG)

    def _create_dispatcher(self):
        self.dispatcher = monitor_db.Dispatcher()

    def tearDown(self):
        self._database.disconnect()
        self._frontend_common_teardown()

    def _set_stubs(self):
        self.mock_config = MockGlobalConfig()
        self.god.stub_with(settings, 'settings', self.mock_config)

        self.mock_drone_manager = MockDroneManager()
        drone_manager._set_instance(self.mock_drone_manager)

        self.mock_email_manager = MockEmailManager()
        self.god.stub_with(mail, "manager", self.mock_email_manager)

        self._database = (
            database_connection.TranslatingDatabase.get_test_database(
                translators=_DB_TRANSLATORS))
        self._database.connect(db_type='django')
        self.god.stub_with(monitor_db, '_db', self._database)
        self.god.stub_with(scheduler_models, '_db', self._database)

        monitor_db.initialize_globals()
        scheduler_models.initialize_globals()

    def _set_settings_values(self):
        self.mock_config.set_config_value('SCHEDULER', 'pidfile_timeout_mins',
                                          1)
        self.mock_config.set_config_value('SCHEDULER', 'gc_stats_interval_mins',
                                          999999)

    def _initialize_test(self):
        self.dispatcher.initialize()

    def _run_dispatcher(self):
        for _ in range(self._A_LOT_OF_TICKS):
            self.dispatcher.tick()

    def test_idle(self):
        self._initialize_test()
        self._run_dispatcher()

    def _assert_process_executed(self, working_directory, pidfile_name):
        process_was_executed = self.mock_drone_manager.was_process_executed(
            'hosts/host1/1-verify', drone_manager.AUTOSERV_PID_FILE)
        self.assert_(process_was_executed,
                     '%s/%s not executed' % (working_directory, pidfile_name))

    def _update_instance(self, model_instance):
        return type(model_instance).objects.get(pk=model_instance.pk)

    def _check_statuses(self, queue_entry, queue_entry_status,
                        host_status=None):
        self._check_entry_status(queue_entry, queue_entry_status)
        if host_status:
            self._check_host_status(queue_entry.host, host_status)

    def _check_entry_status(self, queue_entry, status):
        # update from DB
        queue_entry = self._update_instance(queue_entry)
        self.assertEquals(queue_entry.status, status)

    def _check_host_status(self, host, status):
        # update from DB
        host = self._update_instance(host)
        self.assertEquals(host.status, status)

    def _run_pre_job_verify(self, queue_entry):
        self._run_dispatcher()  # launches verify
        self._check_statuses(queue_entry, HqeStatus.VERIFYING,
                             HostStatus.VERIFYING)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)

    def test_simple_job(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        self._run_pre_job_verify(queue_entry)
        self._run_dispatcher()  # launches job
        self._check_statuses(queue_entry, HqeStatus.RUNNING, HostStatus.RUNNING)
        self._finish_job(queue_entry)
        self._check_statuses(queue_entry, HqeStatus.COMPLETED, HostStatus.READY)
        self._assert_nothing_is_running()

    def _setup_for_pre_job_cleanup(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        job.reboot_before = model_attributes.RebootBefore.ALWAYS
        job.save()
        return queue_entry

    def _run_pre_job_cleanup_job(self, queue_entry):
        self._run_dispatcher()  # cleanup
        self._check_statuses(queue_entry, HqeStatus.VERIFYING,
                             HostStatus.CLEANING)
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self._run_dispatcher()  # verify
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # job
        self._finish_job(queue_entry)

    def test_pre_job_cleanup(self):
        queue_entry = self._setup_for_pre_job_cleanup()
        self._run_pre_job_cleanup_job(queue_entry)

    def _run_pre_job_cleanup_one_failure(self):
        queue_entry = self._setup_for_pre_job_cleanup()
        self._run_dispatcher()  # cleanup
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher()  # repair
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
        self._run_dispatcher()  # second cleanup
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.FAILED,
                             HostStatus.REPAIR_FAILED)
        # nothing else should run
        self._assert_nothing_is_running()

    def _assert_nothing_is_running(self):
        self.assertEquals(self.mock_drone_manager.running_pidfile_ids(), [])

    def _setup_for_post_job_cleanup(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        job.reboot_after = model_attributes.RebootAfter.ALWAYS
        job.save()
        return queue_entry

    def _run_post_job_cleanup_failure_up_to_repair(self, queue_entry,
                                                   include_verify=True):
        if include_verify:
            self._run_pre_job_verify(queue_entry)
        self._run_dispatcher()  # job
        self.mock_drone_manager.finish_process(_PidfileType.JOB)
        self._run_dispatcher()  # parsing + cleanup
        self.mock_drone_manager.finish_process(_PidfileType.PARSE)
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher()  # repair, HQE unaffected
        self.mock_drone_manager.finish_process(_PidfileType.ARCHIVE)
        self._run_dispatcher()
        return queue_entry

    def test_post_job_cleanup_failure(self):
        queue_entry = self._setup_for_post_job_cleanup()
        self._run_post_job_cleanup_failure_up_to_repair(queue_entry)
        self._check_statuses(queue_entry, HqeStatus.COMPLETED,
                             HostStatus.REPAIRING)
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.COMPLETED, HostStatus.READY)

    def test_post_job_cleanup_failure_repair_failure(self):
        queue_entry = self._setup_for_post_job_cleanup()
        self._run_post_job_cleanup_failure_up_to_repair(queue_entry)
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR,
                                               exit_status=256)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.COMPLETED,
                             HostStatus.REPAIR_FAILED)

    def _ensure_post_job_process_is_paired(self, queue_entry, pidfile_type):
        pidfile_name = _PIDFILE_TYPE_TO_PIDFILE[pidfile_type]
        queue_entry = self._update_instance(queue_entry)
        pidfile_id = self.mock_drone_manager.pidfile_from_path(
            queue_entry.execution_path(), pidfile_name)
        self.assert_(pidfile_id._paired_with_pidfile)

    def _finish_job(self, queue_entry):
        self.mock_drone_manager.finish_process(_PidfileType.JOB)
        self._run_dispatcher()  # launches parsing + cleanup
        self._check_statuses(queue_entry, HqeStatus.PARSING,
                             HostStatus.CLEANING)
        self._ensure_post_job_process_is_paired(queue_entry, _PidfileType.PARSE)
        self._finish_parsing_and_cleanup(queue_entry)

    def _finish_parsing_and_cleanup(self, queue_entry):
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self.mock_drone_manager.finish_process(_PidfileType.PARSE)
        self._run_dispatcher()

        self._check_entry_status(queue_entry, HqeStatus.ARCHIVING)
        self.mock_drone_manager.finish_process(_PidfileType.ARCHIVE)
        self._run_dispatcher()

    def _create_reverify_request(self):
        host = self.hosts[0]
        models.SpecialTask.schedule_special_task(
            host=host, task=models.SpecialTask.Task.VERIFY)
        return host

    def test_requested_reverify(self):
        host = self._create_reverify_request()
        self._run_dispatcher()
        self._check_host_status(host, HostStatus.VERIFYING)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()
        self._check_host_status(host, HostStatus.READY)

    def test_requested_reverify_failure(self):
        host = self._create_reverify_request()
        self._run_dispatcher()
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY,
                                               exit_status=256)
        self._run_dispatcher()  # repair
        self._check_host_status(host, HostStatus.REPAIRING)
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR)
        self._run_dispatcher()
        self._check_host_status(host, HostStatus.READY)

    def _setup_for_do_not_verify(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        queue_entry.host.protection = host_protections.Protection.DO_NOT_VERIFY
        queue_entry.host.save()
        return queue_entry

    def test_do_not_verify_job(self):
        queue_entry = self._setup_for_do_not_verify()
        self._run_dispatcher()  # runs job directly
        self._finish_job(queue_entry)

    def test_do_not_verify_job_with_cleanup(self):
        queue_entry = self._setup_for_do_not_verify()
        queue_entry.job.reboot_before = model_attributes.RebootBefore.ALWAYS
        queue_entry.job.save()

        self._run_dispatcher()  # cleanup
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self._run_dispatcher()  # job
        self._finish_job(queue_entry)

    def test_do_not_verify_pre_job_cleanup_failure(self):
        queue_entry = self._setup_for_do_not_verify()
        queue_entry.job.reboot_before = model_attributes.RebootBefore.ALWAYS
        queue_entry.job.save()

        self._run_dispatcher()  # cleanup
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP,
                                               exit_status=256)
        self._run_dispatcher()  # failure ignored; job runs
        self._finish_job(queue_entry)

    def test_do_not_verify_post_job_cleanup_failure(self):
        queue_entry = self._setup_for_do_not_verify()

        self._run_post_job_cleanup_failure_up_to_repair(queue_entry,
                                                        include_verify=False)
        # failure ignored, host still set to Ready
        self._check_statuses(queue_entry, HqeStatus.COMPLETED, HostStatus.READY)
        self._run_dispatcher()  # nothing else runs
        self._assert_nothing_is_running()

    def test_do_not_verify_requested_reverify_failure(self):
        host = self._create_reverify_request()
        host.protection = host_protections.Protection.DO_NOT_VERIFY
        host.save()

        self._run_dispatcher()
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY,
                                               exit_status=256)
        self._run_dispatcher()
        self._check_host_status(host, HostStatus.READY)  # ignore failure
        self._assert_nothing_is_running()

    def test_job_abort_in_verify(self):
        self._initialize_test()
        job = self._create_job(hosts=[1])
        self._run_dispatcher()  # launches verify
        job.hostqueueentry_set.update(aborted=True)
        self._run_dispatcher()  # kills verify, launches cleanup
        self.assert_(self.mock_drone_manager.was_last_process_killed(
            _PidfileType.VERIFY))
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self._run_dispatcher()

    def test_job_abort(self):
        self._initialize_test()
        job = self._create_job(hosts=[1])
        job.run_verify = False
        job.save()

        self._run_dispatcher()  # launches job
        job.hostqueueentry_set.update(aborted=True)
        self._run_dispatcher()  # kills job, launches gathering
        self.assert_(self.mock_drone_manager.was_last_process_killed(
            _PidfileType.JOB))
        self.mock_drone_manager.finish_process(_PidfileType.GATHER)
        self._run_dispatcher()  # launches parsing + cleanup
        queue_entry = job.hostqueueentry_set.all()[0]
        self._finish_parsing_and_cleanup(queue_entry)

    def test_job_abort_queued_synchronous(self):
        self._initialize_test()
        job = self._create_job(hosts=[1, 2])
        job.synch_count = 2
        job.save()

        job.hostqueueentry_set.update(aborted=True)
        self._run_dispatcher()
        for host_queue_entry in job.hostqueueentry_set.all():
            self.assertEqual(host_queue_entry.status,
                             HqeStatus.ABORTED)

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
        models.SpecialTask.objects.create(
            host=queue_entry.host,
            task=models.SpecialTask.Task.VERIFY,
            requested_by=models.User.current_user())
        models.SpecialTask.objects.create(
            host=queue_entry.host,
            task=models.SpecialTask.Task.CLEANUP,
            queue_entry=queue_entry,
            is_complete=True,
            requested_by=models.User.current_user())

        self.assertRaises(host_scheduler.SchedulerError, self._initialize_test)

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

    def test_recover_pending_hqes_with_group(self):
        # recover a group of HQEs that are in Pending, in the same group (e.g.,
        # in a job with atomic hosts)
        job = self._create_job(hosts=[1, 2], atomic_group=1)
        job.save()

        job.hostqueueentry_set.all().update(status=HqeStatus.PENDING)

        self._initialize_test()
        for queue_entry in job.hostqueueentry_set.all():
            self.assertEquals(queue_entry.status, HqeStatus.STARTING)

    def test_recover_parsing(self):
        self._initialize_test()
        job, queue_entry = self._make_job_and_queue_entry()
        job.run_verify = False
        job.reboot_after = model_attributes.RebootAfter.NEVER
        job.save()

        self._run_dispatcher()  # launches job
        self.mock_drone_manager.finish_process(_PidfileType.JOB)
        self._run_dispatcher()  # launches parsing

        # now "restart" the scheduler
        self._create_dispatcher()
        self._initialize_test()
        self._run_dispatcher()
        self.mock_drone_manager.finish_process(_PidfileType.PARSE)
        self._run_dispatcher()

    def test_recover_parsing__no_process_already_aborted(self):
        _, queue_entry = self._make_job_and_queue_entry()
        queue_entry.execution_subdir = 'host1'
        queue_entry.status = HqeStatus.PARSING
        queue_entry.aborted = True
        queue_entry.save()

        self._initialize_test()
        self._run_dispatcher()

    def test_job_scheduled_just_after_abort(self):
        # test a pretty obscure corner case where a job is aborted while queued,
        # another job is ready to run, and throttling is active. the post-abort
        # cleanup must not be pre-empted by the second job.
        job1, queue_entry1 = self._make_job_and_queue_entry()
        job2, queue_entry2 = self._make_job_and_queue_entry()

        self.mock_drone_manager.process_capacity = 0
        self._run_dispatcher()  # schedule job1, but won't start verify
        job1.hostqueueentry_set.update(aborted=True)
        self.mock_drone_manager.process_capacity = 100
        self._run_dispatcher()  # cleanup must run here, not verify for job2
        self._check_statuses(queue_entry1, HqeStatus.ABORTED,
                             HostStatus.CLEANING)
        self.mock_drone_manager.finish_process(_PidfileType.CLEANUP)
        self._run_dispatcher()  # now verify starts for job2
        self._check_statuses(queue_entry2, HqeStatus.VERIFYING,
                             HostStatus.VERIFYING)

    def test_reverify_interrupting_pre_job(self):
        # ensure things behave sanely if a reverify is scheduled in the middle
        # of pre-job actions
        _, queue_entry = self._make_job_and_queue_entry()

        self._run_dispatcher()  # pre-job verify
        self._create_reverify_request()
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY,
                                               exit_status=256)
        self._run_dispatcher()  # repair
        self.mock_drone_manager.finish_process(_PidfileType.REPAIR)
        self._run_dispatcher()  # reverify runs now
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # pre-job verify
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # and job runs...
        self._check_statuses(queue_entry, HqeStatus.RUNNING, HostStatus.RUNNING)
        self._finish_job(queue_entry)  # reverify has been deleted
        self._check_statuses(queue_entry, HqeStatus.COMPLETED,
                             HostStatus.READY)
        self._assert_nothing_is_running()

    def test_reverify_while_job_running(self):
        # once a job is running, a reverify must not be allowed to preempt
        # Gathering
        _, queue_entry = self._make_job_and_queue_entry()
        self._run_pre_job_verify(queue_entry)
        self._run_dispatcher()  # job runs
        self._create_reverify_request()
        # make job end with a signal, so gathering will run
        self.mock_drone_manager.finish_process(_PidfileType.JOB,
                                               exit_status=271)
        self._run_dispatcher()  # gathering must start
        self.mock_drone_manager.finish_process(_PidfileType.GATHER)
        self._run_dispatcher()  # parsing and cleanup
        self._finish_parsing_and_cleanup(queue_entry)
        self._run_dispatcher()  # now reverify runs
        self._check_statuses(queue_entry, HqeStatus.FAILED,
                             HostStatus.VERIFYING)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()
        self._check_host_status(queue_entry.host, HostStatus.READY)

    def test_reverify_while_host_pending(self):
        # ensure that if a reverify is scheduled while a host is in Pending, it
        # won't run until the host is actually free
        job = self._create_job(hosts=[1, 2])
        queue_entry = job.hostqueueentry_set.get(host__hostname='host1')
        job.synch_count = 2
        job.save()

        host2 = self.hosts[1]
        host2.locked = True
        host2.save()

        self._run_dispatcher()  # verify host1
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # host1 Pending
        self._check_statuses(queue_entry, HqeStatus.PENDING, HostStatus.PENDING)
        self._create_reverify_request()
        self._run_dispatcher()  # nothing should happen here
        self._check_statuses(queue_entry, HqeStatus.PENDING, HostStatus.PENDING)

        # now let the job run
        host2.locked = False
        host2.save()
        self._run_dispatcher()  # verify host2
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # run job
        self._finish_job(queue_entry)
        # need to explicitly finish host1's post-job cleanup
        self.mock_drone_manager.finish_specific_process(
            'hosts/host1/4-cleanup', drone_manager.AUTOSERV_PID_FILE)
        self._run_dispatcher()
        # the reverify should now be running
        self._check_statuses(queue_entry, HqeStatus.COMPLETED,
                             HostStatus.VERIFYING)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()
        self._check_host_status(queue_entry.host, HostStatus.READY)

    def test_throttling(self):
        job = self._create_job(hosts=[1, 2, 3])
        job.synch_count = 3
        job.save()

        queue_entries = list(job.hostqueueentry_set.all())

        def _check_hqe_statuses(*statuses):
            for queue_entry, status in zip(queue_entries, statuses):
                self._check_statuses(queue_entry, status)

        self.mock_drone_manager.process_capacity = 2
        self._run_dispatcher()  # verify runs on 1 and 2
        _check_hqe_statuses(HqeStatus.VERIFYING, HqeStatus.VERIFYING,
                            HqeStatus.VERIFYING)
        self.assertEquals(len(self.mock_drone_manager.running_pidfile_ids()), 2)

        self.mock_drone_manager.finish_specific_process(
            'hosts/host1/1-verify', drone_manager.AUTOSERV_PID_FILE)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # verify runs on 3
        _check_hqe_statuses(HqeStatus.PENDING, HqeStatus.PENDING,
                            HqeStatus.VERIFYING)

        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # job won't run due to throttling
        _check_hqe_statuses(HqeStatus.STARTING, HqeStatus.STARTING,
                            HqeStatus.STARTING)
        self._assert_nothing_is_running()

        self.mock_drone_manager.process_capacity = 3
        self._run_dispatcher()  # now job runs
        _check_hqe_statuses(HqeStatus.RUNNING, HqeStatus.RUNNING,
                            HqeStatus.RUNNING)

        self.mock_drone_manager.process_capacity = 2
        self.mock_drone_manager.finish_process(_PidfileType.JOB,
                                               exit_status=271)
        self._run_dispatcher()  # gathering won't run due to throttling
        _check_hqe_statuses(HqeStatus.GATHERING, HqeStatus.GATHERING,
                            HqeStatus.GATHERING)
        self._assert_nothing_is_running()

        self.mock_drone_manager.process_capacity = 3
        self._run_dispatcher()  # now gathering runs

        self.mock_drone_manager.process_capacity = 0
        self.mock_drone_manager.finish_process(_PidfileType.GATHER)
        self._run_dispatcher()  # parsing runs despite throttling
        _check_hqe_statuses(HqeStatus.PARSING, HqeStatus.PARSING,
                            HqeStatus.PARSING)

    def test_abort_starting_while_throttling(self):
        self._initialize_test()
        job = self._create_job(hosts=[1, 2], synchronous=True)
        queue_entry = job.hostqueueentry_set.all()[0]
        job.run_verify = False
        job.reboot_after = model_attributes.RebootAfter.NEVER
        job.save()

        self.mock_drone_manager.process_capacity = 0
        self._run_dispatcher()  # go to starting, but don't start job
        self._check_statuses(queue_entry, HqeStatus.STARTING,
                             HostStatus.PENDING)

        job.hostqueueentry_set.update(aborted=True)
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.GATHERING,
                             HostStatus.RUNNING)

        self.mock_drone_manager.process_capacity = 5
        self._run_dispatcher()
        self._check_statuses(queue_entry, HqeStatus.ABORTED,
                             HostStatus.CLEANING)

    def test_simple_atomic_group_job(self):
        job = self._create_job(atomic_group=1)
        self._run_dispatcher()  # expand + verify
        queue_entries = job.hostqueueentry_set.all()
        self.assertEquals(len(queue_entries), 2)
        self.assertEquals(queue_entries[0].host.hostname, 'host5')
        self.assertEquals(queue_entries[1].host.hostname, 'host6')

        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()  # delay task started waiting

        self.mock_drone_manager.finish_specific_process(
            'hosts/host6/1-verify', drone_manager.AUTOSERV_PID_FILE)
        self._run_dispatcher()  # job starts now
        for entry in queue_entries:
            self._check_statuses(entry, HqeStatus.RUNNING, HostStatus.RUNNING)

        # rest of job proceeds normally

    def test_simple_metahost_assignment(self):
        job = self._create_job(metahosts=[1])
        self._run_dispatcher()
        entry = job.hostqueueentry_set.all()[0]
        self.assertEquals(entry.host.hostname, 'host1')
        self._check_statuses(entry, HqeStatus.VERIFYING, HostStatus.VERIFYING)
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()
        self._check_statuses(entry, HqeStatus.RUNNING, HostStatus.RUNNING)
        # rest of job proceeds normally

    def test_metahost_fail_verify(self):
        self.hosts[1].labels.add(self.labels[0])  # put label1 also on host2
        job = self._create_job(metahosts=[1])
        self._run_dispatcher()  # assigned to host1
        self.mock_drone_manager.finish_process(_PidfileType.VERIFY,
                                               exit_status=256)
        self._run_dispatcher()  # host1 failed, gets reassigned to host2
        entry = job.hostqueueentry_set.all()[0]
        self.assertEquals(entry.host.hostname, 'host2')
        self._check_statuses(entry, HqeStatus.VERIFYING, HostStatus.VERIFYING)
        self._check_host_status(self.hosts[0], HostStatus.REPAIRING)

        self.mock_drone_manager.finish_process(_PidfileType.VERIFY)
        self._run_dispatcher()
        self._check_statuses(entry, HqeStatus.RUNNING, HostStatus.RUNNING)

    def test_hostless_job(self):
        job = self._create_job(hostless=True)
        entry = job.hostqueueentry_set.all()[0]

        self._run_dispatcher()
        self._check_entry_status(entry, HqeStatus.RUNNING)

        self.mock_drone_manager.finish_process(_PidfileType.JOB)
        self._run_dispatcher()
        self._check_entry_status(entry, HqeStatus.PARSING)
        self.mock_drone_manager.finish_process(_PidfileType.PARSE)
        self._run_dispatcher()
        self._check_entry_status(entry, HqeStatus.ARCHIVING)
        self.mock_drone_manager.finish_process(_PidfileType.ARCHIVE)
        self._run_dispatcher()
        self._check_entry_status(entry, HqeStatus.COMPLETED)

    def test_pre_job_keyvals(self):
        job = self._create_job(hosts=[1])
        job.run_verify = False
        job.reboot_before = model_attributes.RebootBefore.NEVER
        job.save()
        models.JobKeyval.objects.create(job=job, key='mykey', value='myvalue')

        self._run_dispatcher()
        self._finish_job(job.hostqueueentry_set.all()[0])

        attached_files = self.mock_drone_manager.attached_files(
            '1-autotest_system/host1')
        job_keyval_path = '1-autotest_system/host1/keyval'
        self.assert_(job_keyval_path in attached_files, attached_files)
        keyval_contents = attached_files[job_keyval_path]
        keyval_dict = dict(line.strip().split('=', 1)
                           for line in keyval_contents.splitlines())
        self.assert_('job_queued' in keyval_dict, keyval_dict)
        self.assertEquals(keyval_dict['mykey'], 'myvalue')


if __name__ == '__main__':
    unittest.main()
