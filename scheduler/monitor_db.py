#!/usr/bin/python -u

"""
Autotest scheduler
"""


import datetime, errno, optparse, os, pwd, Queue, re, shutil, signal
import smtplib, socket, stat, subprocess, sys, tempfile, time, traceback
import itertools, logging, weakref
import common
import MySQLdb
from autotest_lib.scheduler import scheduler_logging_config
from autotest_lib.frontend import setup_django_environment
from autotest_lib.client.common_lib import global_config, logging_manager
from autotest_lib.client.common_lib import host_protections, utils
from autotest_lib.database import database_connection
from autotest_lib.frontend.afe import models, rpc_utils, readonly_connection
from autotest_lib.scheduler import drone_manager, drones, email_manager
from autotest_lib.scheduler import monitor_db_cleanup
from autotest_lib.scheduler import status_server, scheduler_config

BABYSITTER_PID_FILE_PREFIX = 'monitor_db_babysitter'
PID_FILE_PREFIX = 'monitor_db'

RESULTS_DIR = '.'
AUTOSERV_NICE_LEVEL = 10
DB_CONFIG_SECTION = 'AUTOTEST_WEB'
AUTOTEST_PATH = os.path.join(os.path.dirname(__file__), '..')

if os.environ.has_key('AUTOTEST_DIR'):
    AUTOTEST_PATH = os.environ['AUTOTEST_DIR']
AUTOTEST_SERVER_DIR = os.path.join(AUTOTEST_PATH, 'server')
AUTOTEST_TKO_DIR = os.path.join(AUTOTEST_PATH, 'tko')

if AUTOTEST_SERVER_DIR not in sys.path:
    sys.path.insert(0, AUTOTEST_SERVER_DIR)

_AUTOSERV_PID_FILE = '.autoserv_execute'
_CRASHINFO_PID_FILE = '.collect_crashinfo_execute'
_PARSER_PID_FILE = '.parser_execute'

_ALL_PIDFILE_NAMES = (_AUTOSERV_PID_FILE, _CRASHINFO_PID_FILE,
                      _PARSER_PID_FILE)

# error message to leave in results dir when an autoserv process disappears
# mysteriously
_LOST_PROCESS_ERROR = """\
Autoserv failed abnormally during execution for this job, probably due to a
system error on the Autotest server.  Full results may not be available.  Sorry.
"""

_db = None
_shutdown = False
_autoserv_path = os.path.join(drones.AUTOTEST_INSTALL_DIR, 'server', 'autoserv')
_parser_path = os.path.join(drones.AUTOTEST_INSTALL_DIR, 'tko', 'parse')
_testing_mode = False
_base_url = None
_notify_email_statuses = []
_drone_manager = drone_manager.DroneManager()


def _get_pidfile_timeout_secs():
    """@returns How long to wait for autoserv to write pidfile."""
    pidfile_timeout_mins = global_config.global_config.get_config_value(
            scheduler_config.CONFIG_SECTION, 'pidfile_timeout_mins', type=int)
    return pidfile_timeout_mins * 60


def _site_init_monitor_db_dummy():
    return {}


def main():
    try:
        try:
            main_without_exception_handling()
        except SystemExit:
            raise
        except:
            logging.exception('Exception escaping in monitor_db')
            raise
    finally:
        utils.delete_pid_file_if_exists(PID_FILE_PREFIX)


def main_without_exception_handling():
    setup_logging()

    usage = 'usage: %prog [options] results_dir'
    parser = optparse.OptionParser(usage)
    parser.add_option('--recover-hosts', help='Try to recover dead hosts',
                      action='store_true')
    parser.add_option('--test', help='Indicate that scheduler is under ' +
                      'test and should use dummy autoserv and no parsing',
                      action='store_true')
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.print_usage()
        return

    scheduler_enabled = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'enable_scheduler', type=bool)

    if not scheduler_enabled:
        msg = ("Scheduler not enabled, set enable_scheduler to true in the "
               "global_config's SCHEDULER section to enabled it. Exiting.")
        logging.error(msg)
        sys.exit(1)

    global RESULTS_DIR
    RESULTS_DIR = args[0]

    site_init = utils.import_site_function(__file__,
        "autotest_lib.scheduler.site_monitor_db", "site_init_monitor_db",
        _site_init_monitor_db_dummy)
    site_init()

    # Change the cwd while running to avoid issues incase we were launched from
    # somewhere odd (such as a random NFS home directory of the person running
    # sudo to launch us as the appropriate user).
    os.chdir(RESULTS_DIR)

    c = global_config.global_config
    notify_statuses_list = c.get_config_value(scheduler_config.CONFIG_SECTION,
                                              "notify_email_statuses",
                                              default='')
    global _notify_email_statuses
    _notify_email_statuses = [status for status in
                              re.split(r'[\s,;:]', notify_statuses_list.lower())
                              if status]

    if options.test:
        global _autoserv_path
        _autoserv_path = 'autoserv_dummy'
        global _testing_mode
        _testing_mode = True

    # AUTOTEST_WEB.base_url is still a supported config option as some people
    # may wish to override the entire url.
    global _base_url
    config_base_url = c.get_config_value(DB_CONFIG_SECTION, 'base_url',
                                         default='')
    if config_base_url:
        _base_url = config_base_url
    else:
        # For the common case of everything running on a single server you
        # can just set the hostname in a single place in the config file.
        server_name = c.get_config_value('SERVER', 'hostname')
        if not server_name:
            logging.critical('[SERVER] hostname missing from the config file.')
            sys.exit(1)
        _base_url = 'http://%s/afe/' % server_name

    server = status_server.StatusServer(_drone_manager)
    server.start()

    try:
        init()
        dispatcher = Dispatcher()
        dispatcher.initialize(recover_hosts=options.recover_hosts)

        while not _shutdown:
            dispatcher.tick()
            time.sleep(scheduler_config.config.tick_pause_sec)
    except:
        email_manager.manager.log_stacktrace(
            "Uncaught exception; terminating monitor_db")

    email_manager.manager.send_queued_emails()
    server.shutdown()
    _drone_manager.shutdown()
    _db.disconnect()


def setup_logging():
    log_dir = os.environ.get('AUTOTEST_SCHEDULER_LOG_DIR', None)
    log_name = os.environ.get('AUTOTEST_SCHEDULER_LOG_NAME', None)
    logging_manager.configure_logging(
            scheduler_logging_config.SchedulerLoggingConfig(), log_dir=log_dir,
            logfile_name=log_name)


def handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    logging.info("Shutdown request received.")


def init():
    logging.info("%s> dispatcher starting", time.strftime("%X %x"))
    logging.info("My PID is %d", os.getpid())

    if utils.program_is_alive(PID_FILE_PREFIX):
        logging.critical("monitor_db already running, aborting!")
        sys.exit(1)
    utils.write_pid(PID_FILE_PREFIX)

    if _testing_mode:
        global_config.global_config.override_config_value(
            DB_CONFIG_SECTION, 'database', 'stresstest_autotest_web')

    os.environ['PATH'] = AUTOTEST_SERVER_DIR + ':' + os.environ['PATH']
    global _db
    _db = database_connection.DatabaseConnection(DB_CONFIG_SECTION)
    _db.connect()

    # ensure Django connection is in autocommit
    setup_django_environment.enable_autocommit()
    # bypass the readonly connection
    readonly_connection.ReadOnlyConnection.set_globally_disabled(True)

    logging.info("Setting signal handler")
    signal.signal(signal.SIGINT, handle_sigint)

    drones = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'drones', default='localhost')
    drone_list = [hostname.strip() for hostname in drones.split(',')]
    results_host = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'results_host', default='localhost')
    _drone_manager.initialize(RESULTS_DIR, drone_list, results_host)

    logging.info("Connected! Running...")


def _autoserv_command_line(machines, extra_args, job=None, queue_entry=None,
                           verbose=True):
    """
    @returns The autoserv command line as a list of executable + parameters.

    @param machines - string - A machine or comma separated list of machines
            for the (-m) flag.
    @param extra_args - list - Additional arguments to pass to autoserv.
    @param job - Job object - If supplied, -u owner and -l name parameters
            will be added.
    @param queue_entry - A HostQueueEntry object - If supplied and no Job
            object was supplied, this will be used to lookup the Job object.
    """
    autoserv_argv = [_autoserv_path, '-p', '-m', machines,
                     '-r', drone_manager.WORKING_DIRECTORY]
    if job or queue_entry:
        if not job:
            job = queue_entry.job
        autoserv_argv += ['-u', job.owner, '-l', job.name]
    if verbose:
        autoserv_argv.append('--verbose')
    return autoserv_argv + extra_args


class SchedulerError(Exception):
    """Raised by HostScheduler when an inconsistent state occurs."""


class HostScheduler(object):
    def _get_ready_hosts(self):
        # avoid any host with a currently active queue entry against it
        hosts = Host.fetch(
            joins='LEFT JOIN host_queue_entries AS active_hqe '
                  'ON (hosts.id = active_hqe.host_id AND '
                      'active_hqe.active)',
            where="active_hqe.host_id IS NULL "
                  "AND NOT hosts.locked "
                  "AND (hosts.status IS NULL OR hosts.status = 'Ready')")
        return dict((host.id, host) for host in hosts)


    @staticmethod
    def _get_sql_id_list(id_list):
        return ','.join(str(item_id) for item_id in id_list)


    @classmethod
    def _get_many2many_dict(cls, query, id_list, flip=False):
        if not id_list:
            return {}
        query %= cls._get_sql_id_list(id_list)
        rows = _db.execute(query)
        return cls._process_many2many_dict(rows, flip)


    @staticmethod
    def _process_many2many_dict(rows, flip=False):
        result = {}
        for row in rows:
            left_id, right_id = int(row[0]), int(row[1])
            if flip:
                left_id, right_id = right_id, left_id
            result.setdefault(left_id, set()).add(right_id)
        return result


    @classmethod
    def _get_job_acl_groups(cls, job_ids):
        query = """
        SELECT jobs.id, acl_groups_users.aclgroup_id
        FROM jobs
        INNER JOIN users ON users.login = jobs.owner
        INNER JOIN acl_groups_users ON acl_groups_users.user_id = users.id
        WHERE jobs.id IN (%s)
        """
        return cls._get_many2many_dict(query, job_ids)


    @classmethod
    def _get_job_ineligible_hosts(cls, job_ids):
        query = """
        SELECT job_id, host_id
        FROM ineligible_host_queues
        WHERE job_id IN (%s)
        """
        return cls._get_many2many_dict(query, job_ids)


    @classmethod
    def _get_job_dependencies(cls, job_ids):
        query = """
        SELECT job_id, label_id
        FROM jobs_dependency_labels
        WHERE job_id IN (%s)
        """
        return cls._get_many2many_dict(query, job_ids)


    @classmethod
    def _get_host_acls(cls, host_ids):
        query = """
        SELECT host_id, aclgroup_id
        FROM acl_groups_hosts
        WHERE host_id IN (%s)
        """
        return cls._get_many2many_dict(query, host_ids)


    @classmethod
    def _get_label_hosts(cls, host_ids):
        if not host_ids:
            return {}, {}
        query = """
        SELECT label_id, host_id
        FROM hosts_labels
        WHERE host_id IN (%s)
        """ % cls._get_sql_id_list(host_ids)
        rows = _db.execute(query)
        labels_to_hosts = cls._process_many2many_dict(rows)
        hosts_to_labels = cls._process_many2many_dict(rows, flip=True)
        return labels_to_hosts, hosts_to_labels


    @classmethod
    def _get_labels(cls):
        return dict((label.id, label) for label in Label.fetch())


    def refresh(self, pending_queue_entries):
        self._hosts_available = self._get_ready_hosts()

        relevant_jobs = [queue_entry.job_id
                         for queue_entry in pending_queue_entries]
        self._job_acls = self._get_job_acl_groups(relevant_jobs)
        self._ineligible_hosts = self._get_job_ineligible_hosts(relevant_jobs)
        self._job_dependencies = self._get_job_dependencies(relevant_jobs)

        host_ids = self._hosts_available.keys()
        self._host_acls = self._get_host_acls(host_ids)
        self._label_hosts, self._host_labels = self._get_label_hosts(host_ids)

        self._labels = self._get_labels()


    def _is_acl_accessible(self, host_id, queue_entry):
        job_acls = self._job_acls.get(queue_entry.job_id, set())
        host_acls = self._host_acls.get(host_id, set())
        return len(host_acls.intersection(job_acls)) > 0


    def _check_job_dependencies(self, job_dependencies, host_labels):
        missing = job_dependencies - host_labels
        return len(missing) == 0


    def _check_only_if_needed_labels(self, job_dependencies, host_labels,
                                     queue_entry):
        if not queue_entry.meta_host:
            # bypass only_if_needed labels when a specific host is selected
            return True

        for label_id in host_labels:
            label = self._labels[label_id]
            if not label.only_if_needed:
                # we don't care about non-only_if_needed labels
                continue
            if queue_entry.meta_host == label_id:
                # if the label was requested in a metahost it's OK
                continue
            if label_id not in job_dependencies:
                return False
        return True


    def _check_atomic_group_labels(self, host_labels, queue_entry):
        """
        Determine if the given HostQueueEntry's atomic group settings are okay
        to schedule on a host with the given labels.

        @param host_labels: A list of label ids that the host has.
        @param queue_entry: The HostQueueEntry being considered for the host.

        @returns True if atomic group settings are okay, False otherwise.
        """
        return (self._get_host_atomic_group_id(host_labels, queue_entry) ==
                queue_entry.atomic_group_id)


    def _get_host_atomic_group_id(self, host_labels, queue_entry=None):
        """
        Return the atomic group label id for a host with the given set of
        labels if any, or None otherwise.  Raises an exception if more than
        one atomic group are found in the set of labels.

        @param host_labels: A list of label ids that the host has.
        @param queue_entry: The HostQueueEntry we're testing.  Only used for
                extra info in a potential logged error message.

        @returns The id of the atomic group found on a label in host_labels
                or None if no atomic group label is found.
        """
        atomic_labels = [self._labels[label_id] for label_id in host_labels
                         if self._labels[label_id].atomic_group_id is not None]
        atomic_ids = set(label.atomic_group_id for label in atomic_labels)
        if not atomic_ids:
            return None
        if len(atomic_ids) > 1:
            logging.error('More than one Atomic Group on HQE "%s" via: %r',
                          queue_entry, atomic_labels)
        return atomic_ids.pop()


    def _get_atomic_group_labels(self, atomic_group_id):
        """
        Lookup the label ids that an atomic_group is associated with.

        @param atomic_group_id - The id of the AtomicGroup to look up.

        @returns A generator yeilding Label ids for this atomic group.
        """
        return (id for id, label in self._labels.iteritems()
                if label.atomic_group_id == atomic_group_id
                and not label.invalid)


    def _get_eligible_host_ids_in_group(self, group_hosts, queue_entry):
        """
        @param group_hosts - A sequence of Host ids to test for usability
                and eligibility against the Job associated with queue_entry.
        @param queue_entry - The HostQueueEntry that these hosts are being
                tested for eligibility against.

        @returns A subset of group_hosts Host ids that are eligible for the
                supplied queue_entry.
        """
        return set(host_id for host_id in group_hosts
                   if self._is_host_usable(host_id)
                   and self._is_host_eligible_for_job(host_id, queue_entry))


    def _is_host_eligible_for_job(self, host_id, queue_entry):
        if self._is_host_invalid(host_id):
            # if an invalid host is scheduled for a job, it's a one-time host
            # and it therefore bypasses eligibility checks. note this can only
            # happen for non-metahosts, because invalid hosts have their label
            # relationships cleared.
            return True

        job_dependencies = self._job_dependencies.get(queue_entry.job_id, set())
        host_labels = self._host_labels.get(host_id, set())

        return (self._is_acl_accessible(host_id, queue_entry) and
                self._check_job_dependencies(job_dependencies, host_labels) and
                self._check_only_if_needed_labels(
                    job_dependencies, host_labels, queue_entry) and
                self._check_atomic_group_labels(host_labels, queue_entry))


    def _is_host_invalid(self, host_id):
        host_object = self._hosts_available.get(host_id, None)
        return host_object and host_object.invalid


    def _schedule_non_metahost(self, queue_entry):
        if not self._is_host_eligible_for_job(queue_entry.host_id, queue_entry):
            return None
        return self._hosts_available.pop(queue_entry.host_id, None)


    def _is_host_usable(self, host_id):
        if host_id not in self._hosts_available:
            # host was already used during this scheduling cycle
            return False
        if self._hosts_available[host_id].invalid:
            # Invalid hosts cannot be used for metahosts.  They're included in
            # the original query because they can be used by non-metahosts.
            return False
        return True


    def _schedule_metahost(self, queue_entry):
        label_id = queue_entry.meta_host
        hosts_in_label = self._label_hosts.get(label_id, set())
        ineligible_host_ids = self._ineligible_hosts.get(queue_entry.job_id,
                                                         set())

        # must iterate over a copy so we can mutate the original while iterating
        for host_id in list(hosts_in_label):
            if not self._is_host_usable(host_id):
                hosts_in_label.remove(host_id)
                continue
            if host_id in ineligible_host_ids:
                continue
            if not self._is_host_eligible_for_job(host_id, queue_entry):
                continue

            # Remove the host from our cached internal state before returning
            # the host object.
            hosts_in_label.remove(host_id)
            return self._hosts_available.pop(host_id)
        return None


    def find_eligible_host(self, queue_entry):
        if not queue_entry.meta_host:
            assert queue_entry.host_id is not None
            return self._schedule_non_metahost(queue_entry)
        assert queue_entry.atomic_group_id is None
        return self._schedule_metahost(queue_entry)


    def find_eligible_atomic_group(self, queue_entry):
        """
        Given an atomic group host queue entry, locate an appropriate group
        of hosts for the associated job to run on.

        The caller is responsible for creating new HQEs for the additional
        hosts returned in order to run the actual job on them.

        @returns A list of Host instances in a ready state to satisfy this
                atomic group scheduling.  Hosts will all belong to the same
                atomic group label as specified by the queue_entry.
                An empty list will be returned if no suitable atomic
                group could be found.

        TODO(gps): what is responsible for kicking off any attempted repairs on
        a group of hosts?  not this function, but something needs to.  We do
        not communicate that reason for returning [] outside of here...
        For now, we'll just be unschedulable if enough hosts within one group
        enter Repair Failed state.
        """
        assert queue_entry.atomic_group_id is not None
        job = queue_entry.job
        assert job.synch_count and job.synch_count > 0
        atomic_group = queue_entry.atomic_group
        if job.synch_count > atomic_group.max_number_of_machines:
            # Such a Job and HostQueueEntry should never be possible to
            # create using the frontend.  Regardless, we can't process it.
            # Abort it immediately and log an error on the scheduler.
            queue_entry.set_status(models.HostQueueEntry.Status.ABORTED)
            logging.error(
                'Error: job %d synch_count=%d > requested atomic_group %d '
                'max_number_of_machines=%d.  Aborted host_queue_entry %d.',
                job.id, job.synch_count, atomic_group.id,
                 atomic_group.max_number_of_machines, queue_entry.id)
            return []
        hosts_in_label = self._label_hosts.get(queue_entry.meta_host, set())
        ineligible_host_ids = self._ineligible_hosts.get(queue_entry.job_id,
                                                         set())

        # Look in each label associated with atomic_group until we find one with
        # enough hosts to satisfy the job.
        for atomic_label_id in self._get_atomic_group_labels(atomic_group.id):
            group_hosts = set(self._label_hosts.get(atomic_label_id, set()))
            if queue_entry.meta_host is not None:
                # If we have a metahost label, only allow its hosts.
                group_hosts.intersection_update(hosts_in_label)
            group_hosts -= ineligible_host_ids
            eligible_host_ids_in_group = self._get_eligible_host_ids_in_group(
                    group_hosts, queue_entry)

            # Job.synch_count is treated as "minimum synch count" when
            # scheduling for an atomic group of hosts.  The atomic group
            # number of machines is the maximum to pick out of a single
            # atomic group label for scheduling at one time.
            min_hosts = job.synch_count
            max_hosts = atomic_group.max_number_of_machines

            if len(eligible_host_ids_in_group) < min_hosts:
                # Not enough eligible hosts in this atomic group label.
                continue

            eligible_hosts_in_group = [self._hosts_available[id]
                                       for id in eligible_host_ids_in_group]
            # So that they show up in a sane order when viewing the job.
            eligible_hosts_in_group.sort(cmp=Host.cmp_for_sort)

            # Limit ourselves to scheduling the atomic group size.
            if len(eligible_hosts_in_group) > max_hosts:
                eligible_hosts_in_group = eligible_hosts_in_group[:max_hosts]

            # Remove the selected hosts from our cached internal state
            # of available hosts in order to return the Host objects.
            host_list = []
            for host in eligible_hosts_in_group:
                hosts_in_label.discard(host.id)
                self._hosts_available.pop(host.id)
                host_list.append(host)
            return host_list

        return []


class Dispatcher(object):
    def __init__(self):
        self._agents = []
        self._last_clean_time = time.time()
        self._host_scheduler = HostScheduler()
        user_cleanup_time = scheduler_config.config.clean_interval
        self._periodic_cleanup = monitor_db_cleanup.UserCleanup(
            _db, user_cleanup_time)
        self._24hr_upkeep = monitor_db_cleanup.TwentyFourHourUpkeep(_db)
        self._host_agents = {}
        self._queue_entry_agents = {}


    def initialize(self, recover_hosts=True):
        self._periodic_cleanup.initialize()
        self._24hr_upkeep.initialize()

        # always recover processes
        self._recover_processes()

        if recover_hosts:
            self._recover_hosts()


    def tick(self):
        _drone_manager.refresh()
        self._run_cleanup()
        self._find_aborting()
        self._process_recurring_runs()
        self._schedule_delay_tasks()
        self._schedule_new_jobs()
        self._schedule_running_host_queue_entries()
        self._schedule_special_tasks()
        self._handle_agents()
        _drone_manager.execute_actions()
        email_manager.manager.send_queued_emails()


    def _run_cleanup(self):
        self._periodic_cleanup.run_cleanup_maybe()
        self._24hr_upkeep.run_cleanup_maybe()


    def _register_agent_for_ids(self, agent_dict, object_ids, agent):
        for object_id in object_ids:
            agent_dict.setdefault(object_id, set()).add(agent)


    def _unregister_agent_for_ids(self, agent_dict, object_ids, agent):
        for object_id in object_ids:
            assert object_id in agent_dict
            agent_dict[object_id].remove(agent)


    def add_agent(self, agent):
        self._agents.append(agent)
        agent.dispatcher = self
        self._register_agent_for_ids(self._host_agents, agent.host_ids, agent)
        self._register_agent_for_ids(self._queue_entry_agents,
                                     agent.queue_entry_ids, agent)


    def get_agents_for_entry(self, queue_entry):
        """
        Find agents corresponding to the specified queue_entry.
        """
        return list(self._queue_entry_agents.get(queue_entry.id, set()))


    def host_has_agent(self, host):
        """
        Determine if there is currently an Agent present using this host.
        """
        return bool(self._host_agents.get(host.id, None))


    def remove_agent(self, agent):
        self._agents.remove(agent)
        self._unregister_agent_for_ids(self._host_agents, agent.host_ids,
                                       agent)
        self._unregister_agent_for_ids(self._queue_entry_agents,
                                       agent.queue_entry_ids, agent)


    def _host_has_scheduled_special_task(self, host):
        return bool(models.SpecialTask.objects.filter(host__id=host.id,
                                                      is_active=False,
                                                      is_complete=False))


    def _recover_processes(self):
        self._register_pidfiles()
        _drone_manager.refresh()
        self._recover_all_recoverable_entries()
        self._recover_pending_entries()
        self._check_for_remaining_active_entries()
        self._reverify_remaining_hosts()
        # reinitialize drones after killing orphaned processes, since they can
        # leave around files when they die
        _drone_manager.execute_actions()
        _drone_manager.reinitialize_drones()


    def _register_pidfiles(self):
        # during recovery we may need to read pidfiles for both running and
        # parsing entries
        queue_entries = HostQueueEntry.fetch(
            where="status IN ('Running', 'Gathering', 'Parsing')")
        special_tasks = models.SpecialTask.objects.filter(is_active=True)
        for execution_entry in itertools.chain(queue_entries, special_tasks):
            for pidfile_name in _ALL_PIDFILE_NAMES:
                pidfile_id = _drone_manager.get_pidfile_id_from(
                    execution_entry.execution_path(), pidfile_name=pidfile_name)
                _drone_manager.register_pidfile(pidfile_id)


    def _get_recovery_run_monitor(self, execution_path, pidfile_name, orphans):
        run_monitor = PidfileRunMonitor()
        run_monitor.attach_to_existing_process(execution_path,
                                               pidfile_name=pidfile_name)
        if run_monitor.has_process():
            orphans.discard(run_monitor.get_process())
            return run_monitor, '(process %s)' % run_monitor.get_process()
        return None, 'without process'


    def _get_unassigned_entries(self, status):
        for entry in HostQueueEntry.fetch(where="status = '%s'" % status):
            if not self.get_agents_for_entry(entry):
                yield entry


    def _recover_entries_with_status(self, status, orphans, pidfile_name,
                                     recover_entries_fn):
        for queue_entry in self._get_unassigned_entries(status):
            queue_entries = queue_entry.job.get_group_entries(queue_entry)
            run_monitor, process_string = self._get_recovery_run_monitor(
                    queue_entry.execution_path(), pidfile_name, orphans)
            if not run_monitor:
                # _schedule_running_host_queue_entries should schedule and
                # recover these entries
                continue

            logging.info('Recovering %s entry %s %s',status.lower(),
                         ', '.join(str(entry) for entry in queue_entries),
                         process_string)
            recover_entries_fn(queue_entry.job, queue_entries, run_monitor)


    def _check_for_remaining_orphan_processes(self, orphans):
        if not orphans:
            return
        subject = 'Unrecovered orphan autoserv processes remain'
        message = '\n'.join(str(process) for process in orphans)
        email_manager.manager.enqueue_notify_email(subject, message)

        die_on_orphans = global_config.global_config.get_config_value(
            scheduler_config.CONFIG_SECTION, 'die_on_orphans', type=bool)

        if die_on_orphans:
            raise RuntimeError(subject + '\n' + message)


    def _recover_running_entries(self, orphans):
        def recover_entries(job, queue_entries, run_monitor):
            queue_task = QueueTask(job=job, queue_entries=queue_entries,
                                   recover_run_monitor=run_monitor)
            self.add_agent(Agent(task=queue_task,
                                 num_processes=len(queue_entries)))

        self._recover_entries_with_status(models.HostQueueEntry.Status.RUNNING,
                                          orphans, _AUTOSERV_PID_FILE,
                                          recover_entries)


    def _recover_gathering_entries(self, orphans):
        def recover_entries(job, queue_entries, run_monitor):
            gather_task = GatherLogsTask(job, queue_entries,
                                         recover_run_monitor=run_monitor)
            self.add_agent(Agent(gather_task))

        self._recover_entries_with_status(
            models.HostQueueEntry.Status.GATHERING,
            orphans, _CRASHINFO_PID_FILE, recover_entries)


    def _recover_parsing_entries(self, orphans):
        def recover_entries(job, queue_entries, run_monitor):
            reparse_task = FinalReparseTask(queue_entries,
                                            recover_run_monitor=run_monitor)
            self.add_agent(Agent(reparse_task, num_processes=0))

        self._recover_entries_with_status(models.HostQueueEntry.Status.PARSING,
                                          orphans, _PARSER_PID_FILE,
                                          recover_entries)


    def _recover_pending_entries(self):
        for entry in self._get_unassigned_entries(
                models.HostQueueEntry.Status.PENDING):
            entry.on_pending()


    def _recover_all_recoverable_entries(self):
        orphans = _drone_manager.get_orphaned_autoserv_processes()
        self._recover_running_entries(orphans)
        self._recover_gathering_entries(orphans)
        self._recover_parsing_entries(orphans)
        self._recover_special_tasks(orphans)
        self._check_for_remaining_orphan_processes(orphans)


    def _recover_special_tasks(self, orphans):
        """\
        Recovers all special tasks that have started running but have not
        completed.
        """

        tasks = models.SpecialTask.objects.filter(is_active=True,
                                                  is_complete=False)
        # Use ordering to force NULL queue_entry_id's to the end of the list
        for task in tasks.order_by('-queue_entry__id'):
            if self.host_has_agent(task.host):
                raise SchedulerError(
                        "%s already has a host agent %s." % (
                                task, self._host_agents.get(task.host.id)))

            run_monitor, process_string = self._get_recovery_run_monitor(
                    task.execution_path(), _AUTOSERV_PID_FILE, orphans)

            logging.info('Recovering %s %s', task, process_string)
            self._recover_special_task(task, run_monitor)


    def _recover_special_task(self, task, run_monitor):
        """\
        Recovers a single special task.
        """
        if task.task == models.SpecialTask.Task.VERIFY:
            agent_task = self._recover_verify(task, run_monitor)
        elif task.task == models.SpecialTask.Task.REPAIR:
            agent_task = self._recover_repair(task, run_monitor)
        elif task.task == models.SpecialTask.Task.CLEANUP:
            agent_task = self._recover_cleanup(task, run_monitor)
        else:
            # Should never happen
            logging.error(
                "Special task id %d had invalid task %s", (task.id, task.task))

        self.add_agent(Agent(agent_task))


    def _recover_verify(self, task, run_monitor):
        """\
        Recovers a verify task.
        No associated queue entry: Verify host
        With associated queue entry: Verify host, and run associated queue
                                     entry
        """
        return VerifyTask(task=task, recover_run_monitor=run_monitor)


    def _recover_repair(self, task, run_monitor):
        """\
        Recovers a repair task.
        Always repair host
        """
        return RepairTask(task=task, recover_run_monitor=run_monitor)


    def _recover_cleanup(self, task, run_monitor):
        """\
        Recovers a cleanup task.
        No associated queue entry: Clean host
        With associated queue entry: Clean host, verify host if needed, and
                                     run associated queue entry
        """
        return CleanupTask(task=task, recover_run_monitor=run_monitor)


    def _check_for_remaining_active_entries(self):
        queue_entries = HostQueueEntry.fetch(
                where='active AND NOT complete AND status NOT IN '
                      '("Starting", "Gathering", "Pending")')

        unrecovered_active_hqes = [entry for entry in queue_entries
                                   if not self.get_agents_for_entry(entry) and
                                      not self._host_has_scheduled_special_task(
                                              entry.host)]
        if unrecovered_active_hqes:
            message = '\n'.join(str(hqe) for hqe in unrecovered_active_hqes)
            raise SchedulerError(
                    '%d unrecovered active host queue entries:\n%s' %
                    (len(unrecovered_active_hqes), message))


    def _schedule_special_tasks(self):
        tasks = models.SpecialTask.objects.filter(is_active=False,
                                                  is_complete=False,
                                                  host__locked=False)
        # We want lower ids to come first, but the NULL queue_entry_ids need to
        # come last
        tasks = tasks.extra(select={'isnull' : 'queue_entry_id IS NULL'})
        tasks = tasks.extra(order_by=['isnull', 'id'])

        for task in tasks:
            if self.host_has_agent(task.host):
                continue

            if task.task == models.SpecialTask.Task.CLEANUP:
                    agent_task = CleanupTask(task=task)
            elif task.task == models.SpecialTask.Task.VERIFY:
                    agent_task = VerifyTask(task=task)
            elif task.task == models.SpecialTask.Task.REPAIR:
                agent_task = RepairTask(task=task)
            else:
                email_manager.manager.enqueue_notify_email(
                        'Special task with invalid task', task)
                continue

            self.add_agent(Agent(agent_task))


    def _reverify_remaining_hosts(self):
        # recover active hosts that have not yet been recovered, although this
        # should never happen
        message = ('Recovering active host %s - this probably indicates a '
                   'scheduler bug')
        self._reverify_hosts_where(
                "status IN ('Repairing', 'Verifying', 'Cleaning')",
                print_message=message)


    def _reverify_hosts_where(self, where,
                              print_message='Reverifying host %s'):
        full_where='locked = 0 AND invalid = 0 AND ' + where
        for host in Host.fetch(where=full_where):
            if self.host_has_agent(host):
                # host has already been recovered in some way
                continue
            if self._host_has_scheduled_special_task(host):
                # host will have a special task scheduled on the next cycle
                continue
            if print_message:
                logging.info(print_message, host.hostname)
            models.SpecialTask.objects.create(
                    task=models.SpecialTask.Task.CLEANUP,
                    host=models.Host(id=host.id))


    def _recover_hosts(self):
        # recover "Repair Failed" hosts
        message = 'Reverifying dead host %s'
        self._reverify_hosts_where("status = 'Repair Failed'",
                                   print_message=message)



    def _get_pending_queue_entries(self):
        # prioritize by job priority, then non-metahost over metahost, then FIFO
        return list(HostQueueEntry.fetch(
            joins='INNER JOIN jobs ON (job_id=jobs.id)',
            where='NOT complete AND NOT active AND status="Queued"',
            order_by='jobs.priority DESC, meta_host, job_id'))


    def _refresh_pending_queue_entries(self):
        """
        Lookup the pending HostQueueEntries and call our HostScheduler
        refresh() method given that list.  Return the list.

        @returns A list of pending HostQueueEntries sorted in priority order.
        """
        queue_entries = self._get_pending_queue_entries()
        if not queue_entries:
            return []

        self._host_scheduler.refresh(queue_entries)

        return queue_entries


    def _schedule_atomic_group(self, queue_entry):
        """
        Schedule the given queue_entry on an atomic group of hosts.

        Returns immediately if there are insufficient available hosts.

        Creates new HostQueueEntries based off of queue_entry for the
        scheduled hosts and starts them all running.
        """
        # This is a virtual host queue entry representing an entire
        # atomic group, find a group and schedule their hosts.
        group_hosts = self._host_scheduler.find_eligible_atomic_group(
                queue_entry)
        if not group_hosts:
            return

        logging.info('Expanding atomic group entry %s with hosts %s',
                     queue_entry,
                     ', '.join(host.hostname for host in group_hosts))
        # The first assigned host uses the original HostQueueEntry
        group_queue_entries = [queue_entry]
        for assigned_host in group_hosts[1:]:
            # Create a new HQE for every additional assigned_host.
            new_hqe = HostQueueEntry.clone(queue_entry)
            new_hqe.save()
            group_queue_entries.append(new_hqe)
        assert len(group_queue_entries) == len(group_hosts)
        for queue_entry, host in itertools.izip(group_queue_entries,
                                                group_hosts):
            self._run_queue_entry(queue_entry, host)


    def _schedule_new_jobs(self):
        queue_entries = self._refresh_pending_queue_entries()
        if not queue_entries:
            return

        for queue_entry in queue_entries:
            if (queue_entry.atomic_group_id is None or
                queue_entry.host_id is not None):
                assigned_host = self._host_scheduler.find_eligible_host(
                        queue_entry)
                if assigned_host:
                    self._run_queue_entry(queue_entry, assigned_host)
            else:
                self._schedule_atomic_group(queue_entry)


    def _schedule_running_host_queue_entries(self):
        entries = HostQueueEntry.fetch(
                where="status IN "
                      "('Starting', 'Running', 'Gathering', 'Parsing')")
        for entry in entries:
            if self.get_agents_for_entry(entry):
                continue

            task_entries = entry.job.get_group_entries(entry)
            for task_entry in task_entries:
                if (task_entry.status != models.HostQueueEntry.Status.PARSING
                        and self.host_has_agent(task_entry.host)):
                    agent = self._host_agents.get(task_entry.host.id)[0]
                    raise SchedulerError('Attempted to schedule on host that '
                                         'already has agent: %s (previous '
                                         'agent task: %s)'
                                         % (task_entry, agent.task))

            if entry.status in (models.HostQueueEntry.Status.STARTING,
                                models.HostQueueEntry.Status.RUNNING):
                params = entry.job.get_autoserv_params(task_entries)
                agent_task = QueueTask(job=entry.job,
                                       queue_entries=task_entries, cmd=params)
            elif entry.status == models.HostQueueEntry.Status.GATHERING:
                agent_task = GatherLogsTask(
                        job=entry.job, queue_entries=task_entries)
            elif entry.status == models.HostQueueEntry.Status.PARSING:
                agent_task = FinalReparseTask(queue_entries=task_entries)
            else:
                raise SchedulerError('_schedule_running_host_queue_entries got '
                                     'entry with invalid status %s: %s'
                                     % (entry.status, entry))

            self.add_agent(Agent(agent_task, num_processes=len(task_entries)))


    def _schedule_delay_tasks(self):
        for entry in HostQueueEntry.fetch(where="status = 'Waiting'"):
            task = entry.job.schedule_delayed_callback_task(entry)
            if task:
                self.add_agent(Agent(task, num_processes=0))


    def _run_queue_entry(self, queue_entry, host):
        queue_entry.schedule_pre_job_tasks(assigned_host=host)


    def _find_aborting(self):
        for entry in HostQueueEntry.fetch(where='aborted and not complete'):
            logging.info('Aborting %s', entry)
            for agent in self.get_agents_for_entry(entry):
                agent.abort()
            entry.abort(self)


    def _can_start_agent(self, agent, num_started_this_cycle,
                         have_reached_limit):
        # always allow zero-process agents to run
        if agent.num_processes == 0:
            return True
        # don't allow any nonzero-process agents to run after we've reached a
        # limit (this avoids starvation of many-process agents)
        if have_reached_limit:
            return False
        # total process throttling
        if agent.num_processes > _drone_manager.max_runnable_processes():
            return False
        # if a single agent exceeds the per-cycle throttling, still allow it to
        # run when it's the first agent in the cycle
        if num_started_this_cycle == 0:
            return True
        # per-cycle throttling
        if (num_started_this_cycle + agent.num_processes >
            scheduler_config.config.max_processes_started_per_cycle):
            return False
        return True


    def _handle_agents(self):
        num_started_this_cycle = 0
        have_reached_limit = False
        # iterate over copy, so we can remove agents during iteration
        for agent in list(self._agents):
            if not agent.started:
                if not self._can_start_agent(agent, num_started_this_cycle,
                                             have_reached_limit):
                    have_reached_limit = True
                    continue
                num_started_this_cycle += agent.num_processes
            agent.tick()
            if agent.is_done():
                logging.info("agent finished")
                self.remove_agent(agent)
        logging.info('%d running processes',
                     _drone_manager.total_running_processes())


    def _process_recurring_runs(self):
        recurring_runs = models.RecurringRun.objects.filter(
            start_date__lte=datetime.datetime.now())
        for rrun in recurring_runs:
            # Create job from template
            job = rrun.job
            info = rpc_utils.get_job_info(job)
            options = job.get_object_dict()

            host_objects = info['hosts']
            one_time_hosts = info['one_time_hosts']
            metahost_objects = info['meta_hosts']
            dependencies = info['dependencies']
            atomic_group = info['atomic_group']

            for host in one_time_hosts or []:
                this_host = models.Host.create_one_time_host(host.hostname)
                host_objects.append(this_host)

            try:
                rpc_utils.create_new_job(owner=rrun.owner.login,
                                         options=options,
                                         host_objects=host_objects,
                                         metahost_objects=metahost_objects,
                                         atomic_group=atomic_group)

            except Exception, ex:
                logging.exception(ex)
                #TODO send email

            if rrun.loop_count == 1:
                rrun.delete()
            else:
                if rrun.loop_count != 0: # if not infinite loop
                    # calculate new start_date
                    difference = datetime.timedelta(seconds=rrun.loop_period)
                    rrun.start_date = rrun.start_date + difference
                    rrun.loop_count -= 1
                    rrun.save()


class PidfileRunMonitor(object):
    """
    Client must call either run() to start a new process or
    attach_to_existing_process().
    """

    class _PidfileException(Exception):
        """
        Raised when there's some unexpected behavior with the pid file, but only
        used internally (never allowed to escape this class).
        """


    def __init__(self):
        self.lost_process = False
        self._start_time = None
        self.pidfile_id = None
        self._state = drone_manager.PidfileContents()


    def _add_nice_command(self, command, nice_level):
        if not nice_level:
            return command
        return ['nice', '-n', str(nice_level)] + command


    def _set_start_time(self):
        self._start_time = time.time()


    def run(self, command, working_directory, nice_level=None, log_file=None,
            pidfile_name=None, paired_with_pidfile=None):
        assert command is not None
        if nice_level is not None:
            command = ['nice', '-n', str(nice_level)] + command
        self._set_start_time()
        self.pidfile_id = _drone_manager.execute_command(
            command, working_directory, pidfile_name=pidfile_name,
            log_file=log_file, paired_with_pidfile=paired_with_pidfile)


    def attach_to_existing_process(self, execution_path,
                                   pidfile_name=_AUTOSERV_PID_FILE):
        self._set_start_time()
        self.pidfile_id = _drone_manager.get_pidfile_id_from(
            execution_path, pidfile_name=pidfile_name)
        _drone_manager.register_pidfile(self.pidfile_id)


    def kill(self):
        if self.has_process():
            _drone_manager.kill_process(self.get_process())


    def has_process(self):
        self._get_pidfile_info()
        return self._state.process is not None


    def get_process(self):
        self._get_pidfile_info()
        assert self._state.process is not None
        return self._state.process


    def _read_pidfile(self, use_second_read=False):
        assert self.pidfile_id is not None, (
            'You must call run() or attach_to_existing_process()')
        contents = _drone_manager.get_pidfile_contents(
            self.pidfile_id, use_second_read=use_second_read)
        if contents.is_invalid():
            self._state = drone_manager.PidfileContents()
            raise self._PidfileException(contents)
        self._state = contents


    def _handle_pidfile_error(self, error, message=''):
        message = error + '\nProcess: %s\nPidfile: %s\n%s' % (
            self._state.process, self.pidfile_id, message)
        email_manager.manager.enqueue_notify_email(error, message)
        self.on_lost_process(self._state.process)


    def _get_pidfile_info_helper(self):
        if self.lost_process:
            return

        self._read_pidfile()

        if self._state.process is None:
            self._handle_no_process()
            return

        if self._state.exit_status is None:
            # double check whether or not autoserv is running
            if _drone_manager.is_process_running(self._state.process):
                return

            # pid but no running process - maybe process *just* exited
            self._read_pidfile(use_second_read=True)
            if self._state.exit_status is None:
                # autoserv exited without writing an exit code
                # to the pidfile
                self._handle_pidfile_error(
                    'autoserv died without writing exit code')


    def _get_pidfile_info(self):
        """\
        After completion, self._state will contain:
         pid=None, exit_status=None if autoserv has not yet run
         pid!=None, exit_status=None if autoserv is running
         pid!=None, exit_status!=None if autoserv has completed
        """
        try:
            self._get_pidfile_info_helper()
        except self._PidfileException, exc:
            self._handle_pidfile_error('Pidfile error', traceback.format_exc())


    def _handle_no_process(self):
        """\
        Called when no pidfile is found or no pid is in the pidfile.
        """
        message = 'No pid found at %s' % self.pidfile_id
        if time.time() - self._start_time > _get_pidfile_timeout_secs():
            email_manager.manager.enqueue_notify_email(
                'Process has failed to write pidfile', message)
            self.on_lost_process()


    def on_lost_process(self, process=None):
        """\
        Called when autoserv has exited without writing an exit status,
        or we've timed out waiting for autoserv to write a pid to the
        pidfile.  In either case, we just return failure and the caller
        should signal some kind of warning.

        process is unimportant here, as it shouldn't be used by anyone.
        """
        self.lost_process = True
        self._state.process = process
        self._state.exit_status = 1
        self._state.num_tests_failed = 0


    def exit_code(self):
        self._get_pidfile_info()
        return self._state.exit_status


    def num_tests_failed(self):
        """@returns The number of tests that failed or -1 if unknown."""
        self._get_pidfile_info()
        if self._state.num_tests_failed is None:
            return -1
        return self._state.num_tests_failed


    def try_copy_results_on_drone(self, **kwargs):
        if self.has_process():
            # copy results logs into the normal place for job results
            _drone_manager.copy_results_on_drone(self.get_process(), **kwargs)


    def try_copy_to_results_repository(self, source, **kwargs):
        if self.has_process():
            _drone_manager.copy_to_results_repository(self.get_process(),
                                                      source, **kwargs)


class Agent(object):
    """
    An agent for use by the Dispatcher class to perform a task.

    The following methods are required on all task objects:
        poll() - Called periodically to let the task check its status and
                update its internal state.  If the task succeeded.
        is_done() - Returns True if the task is finished.
        abort() - Called when an abort has been requested.  The task must
                set its aborted attribute to True if it actually aborted.

    The following attributes are required on all task objects:
        aborted - bool, True if this task was aborted.
        success - bool, True if this task succeeded.
        queue_entry_ids - A sequence of HostQueueEntry ids this task handles.
        host_ids - A sequence of Host ids this task represents.

    The following attribute is written to all task objects:
        agent - A reference to the Agent instance that the task has been
                added to.
    """


    def __init__(self, task, num_processes=1):
        """
        @param task: A task as described in the class docstring.
        @param num_processes: The number of subprocesses the Agent represents.
                This is used by the Dispatcher for managing the load on the
                system.  Defaults to 1.
        """
        self.task = task
        task.agent = self

        # This is filled in by Dispatcher.add_agent()
        self.dispatcher = None
        self.num_processes = num_processes

        self.queue_entry_ids = task.queue_entry_ids
        self.host_ids = task.host_ids

        self.started = False


    def tick(self):
        self.started = True
        if self.task:
            self.task.poll()
            if self.task.is_done():
                self.task = None


    def is_done(self):
        return self.task is None


    def abort(self):
        if self.task:
            self.task.abort()
            if self.task.aborted:
                # tasks can choose to ignore aborts
                self.task = None


class DelayedCallTask(object):
    """
    A task object like AgentTask for an Agent to run that waits for the
    specified amount of time to have elapsed before calling the supplied
    callback once and finishing.  If the callback returns anything, it is
    assumed to be a new Agent instance and will be added to the dispatcher.

    @attribute end_time: The absolute posix time after which this task will
            call its callback when it is polled and be finished.

    Also has all attributes required by the Agent class.
    """
    def __init__(self, delay_seconds, callback, now_func=None):
        """
        @param delay_seconds: The delay in seconds from now that this task
                will call the supplied callback and be done.
        @param callback: A callable to be called by this task once after at
                least delay_seconds time has elapsed.  It must return None
                or a new Agent instance.
        @param now_func: A time.time like function.  Default: time.time.
                Used for testing.
        """
        assert delay_seconds > 0
        assert callable(callback)
        if not now_func:
            now_func = time.time
        self._now_func = now_func
        self._callback = callback

        self.end_time = self._now_func() + delay_seconds

        # These attributes are required by Agent.
        self.aborted = False
        self.host_ids = ()
        self.success = False
        self.queue_entry_ids = ()
        # This is filled in by Agent.add_task().
        self.agent = None


    def poll(self):
        if not self.is_done() and self._now_func() >= self.end_time:
            self._callback()
            self.success = True


    def is_done(self):
        return self.success or self.aborted


    def abort(self):
        self.aborted = True


class AgentTask(object):
    def __init__(self, cmd=None, working_directory=None,
                 pidfile_name=None, paired_with_pidfile=None,
                 recover_run_monitor=None):
        self.done = False
        self.cmd = cmd
        self._working_directory = working_directory
        self.agent = None
        self.monitor = recover_run_monitor
        self.started = bool(recover_run_monitor)
        self.success = None
        self.aborted = False
        self.queue_entry_ids = []
        self.host_ids = []
        self.log_file = None


    def _set_ids(self, host=None, queue_entries=None):
        if queue_entries and queue_entries != [None]:
            self.host_ids = [entry.host.id for entry in queue_entries]
            self.queue_entry_ids = [entry.id for entry in queue_entries]
        else:
            assert host
            self.host_ids = [host.id]


    def poll(self):
        if not self.started:
            self.start()
        self.tick()


    def tick(self):
        if self.monitor:
            exit_code = self.monitor.exit_code()
            if exit_code is None:
                return
            success = (exit_code == 0)
        else:
            success = False

        self.finished(success)


    def is_done(self):
        return self.done


    def finished(self, success):
        if self.done:
            return
        self.done = True
        self.success = success
        self.epilog()


    def prolog(self):
        assert not self.monitor


    def cleanup(self):
        if self.monitor and self.log_file:
            self.monitor.try_copy_to_results_repository(self.log_file)


    def epilog(self):
        self.cleanup()


    def start(self):
        assert self.agent

        if not self.started:
            self.prolog()
            self.run()

        self.started = True


    def abort(self):
        if self.monitor:
            self.monitor.kill()
        self.done = True
        self.aborted = True
        self.cleanup()


    def _get_consistent_execution_path(self, execution_entries):
        first_execution_path = execution_entries[0].execution_path()
        for execution_entry in execution_entries[1:]:
            assert execution_entry.execution_path() == first_execution_path, (
                '%s (%s) != %s (%s)' % (execution_entry.execution_path(),
                                        execution_entry,
                                        first_execution_path,
                                        execution_entries[0]))
        return first_execution_path


    def _copy_results(self, execution_entries, use_monitor=None):
        """
        @param execution_entries: list of objects with execution_path() method
        """
        if use_monitor is not None and not use_monitor.has_process():
            return

        assert len(execution_entries) > 0
        if use_monitor is None:
            assert self.monitor
            use_monitor = self.monitor
        assert use_monitor.has_process()
        execution_path = self._get_consistent_execution_path(execution_entries)
        results_path = execution_path + '/'
        use_monitor.try_copy_to_results_repository(results_path)


    def _parse_results(self, queue_entries):
        for queue_entry in queue_entries:
            queue_entry.set_status(models.HostQueueEntry.Status.PARSING)


    def _copy_and_parse_results(self, queue_entries, use_monitor=None):
        self._copy_results(queue_entries, use_monitor)
        self._parse_results(queue_entries)


    def run(self, pidfile_name=_AUTOSERV_PID_FILE, paired_with_pidfile=None):
        assert not self.monitor
        if self.cmd:
            self.monitor = PidfileRunMonitor()
            self.monitor.run(self.cmd, self._working_directory,
                             nice_level=AUTOSERV_NICE_LEVEL,
                             log_file=self.log_file,
                             pidfile_name=pidfile_name,
                             paired_with_pidfile=paired_with_pidfile)


class TaskWithJobKeyvals(object):
    """AgentTask mixin providing functionality to help with job keyval files."""
    _KEYVAL_FILE = 'keyval'
    def _format_keyval(self, key, value):
        return '%s=%s' % (key, value)


    def _keyval_path(self):
        """Subclasses must override this"""
        raise NotImplemented


    def _write_keyval_after_job(self, field, value):
        assert self.monitor
        if not self.monitor.has_process():
            return
        _drone_manager.write_lines_to_file(
            self._keyval_path(), [self._format_keyval(field, value)],
            paired_with_process=self.monitor.get_process())


    def _job_queued_keyval(self, job):
        return 'job_queued', int(time.mktime(job.created_on.timetuple()))


    def _write_job_finished(self):
        self._write_keyval_after_job("job_finished", int(time.time()))


    def _write_keyvals_before_job_helper(self, keyval_dict, keyval_path):
        keyval_contents = '\n'.join(self._format_keyval(key, value)
                                    for key, value in keyval_dict.iteritems())
        # always end with a newline to allow additional keyvals to be written
        keyval_contents += '\n'
        _drone_manager.attach_file_to_execution(self._working_directory,
                                                keyval_contents,
                                                file_path=keyval_path)


    def _write_keyvals_before_job(self, keyval_dict):
        self._write_keyvals_before_job_helper(keyval_dict, self._keyval_path())


    def _write_host_keyvals(self, host):
        keyval_path = os.path.join(self._working_directory, 'host_keyvals',
                                   host.hostname)
        platform, all_labels = host.platform_and_labels()
        keyval_dict = dict(platform=platform, labels=','.join(all_labels))
        self._write_keyvals_before_job_helper(keyval_dict, keyval_path)


class SpecialAgentTask(AgentTask, TaskWithJobKeyvals):
    """
    Subclass for AgentTasks that correspond to a SpecialTask entry in the DB.
    """

    TASK_TYPE = None
    host = None
    queue_entry = None

    def __init__(self, task, extra_command_args, **kwargs):
        assert (self.TASK_TYPE is not None,
                'self.TASK_TYPE must be overridden')

        self.host = Host(id=task.host.id)
        self.queue_entry = None
        if task.queue_entry:
            self.queue_entry = HostQueueEntry(id=task.queue_entry.id)

        self.task = task
        kwargs['working_directory'] = task.execution_path()
        self._extra_command_args = extra_command_args
        super(SpecialAgentTask, self).__init__(**kwargs)


    def _keyval_path(self):
        return os.path.join(self._working_directory, self._KEYVAL_FILE)


    def prolog(self):
        super(SpecialAgentTask, self).prolog()
        self.cmd = _autoserv_command_line(self.host.hostname,
                                          self._extra_command_args,
                                          queue_entry=self.queue_entry)
        self._working_directory = self.task.execution_path()
        self.task.activate()
        self._write_host_keyvals(self.host)


    def _fail_queue_entry(self):
        assert self.queue_entry

        if self.queue_entry.meta_host:
            return # don't fail metahost entries, they'll be reassigned

        self.queue_entry.update_from_database()
        if self.queue_entry.status != models.HostQueueEntry.Status.QUEUED:
            return # entry has been aborted

        self.queue_entry.set_execution_subdir()
        queued_key, queued_time = self._job_queued_keyval(
            self.queue_entry.job)
        self._write_keyval_after_job(queued_key, queued_time)
        self._write_job_finished()

        # copy results logs into the normal place for job results
        self.monitor.try_copy_results_on_drone(
                source_path=self._working_directory + '/',
                destination_path=self.queue_entry.execution_path() + '/')

        self._copy_results([self.queue_entry])
        self.queue_entry.handle_host_failure()
        if self.queue_entry.job.parse_failed_repair:
            self._parse_results([self.queue_entry])

        pidfile_id = _drone_manager.get_pidfile_id_from(
                self.queue_entry.execution_path(),
                pidfile_name=_AUTOSERV_PID_FILE)
        _drone_manager.register_pidfile(pidfile_id)


    def cleanup(self):
        super(SpecialAgentTask, self).cleanup()
        self.task.finish()
        if self.monitor and self.monitor.has_process():
            self._copy_results([self.task])


class RepairTask(SpecialAgentTask):
    TASK_TYPE = models.SpecialTask.Task.REPAIR


    def __init__(self, task, recover_run_monitor=None):
        """\
        queue_entry: queue entry to mark failed if this repair fails.
        """
        protection = host_protections.Protection.get_string(
                task.host.protection)
        # normalize the protection name
        protection = host_protections.Protection.get_attr_name(protection)

        super(RepairTask, self).__init__(
                task, ['-R', '--host-protection', protection],
                recover_run_monitor=recover_run_monitor)

        # *don't* include the queue entry in IDs -- if the queue entry is
        # aborted, we want to leave the repair task running
        self._set_ids(host=self.host)


    def prolog(self):
        super(RepairTask, self).prolog()
        logging.info("repair_task starting")
        self.host.set_status(models.Host.Status.REPAIRING)


    def epilog(self):
        super(RepairTask, self).epilog()

        if self.success:
            self.host.set_status(models.Host.Status.READY)
        else:
            self.host.set_status(models.Host.Status.REPAIR_FAILED)
            if self.queue_entry:
                self._fail_queue_entry()


class PreJobTask(SpecialAgentTask):
    def _copy_to_results_repository(self):
        if not self.queue_entry or self.queue_entry.meta_host:
            return

        self.queue_entry.set_execution_subdir()
        log_name = os.path.basename(self.task.execution_path())
        source = os.path.join(self.task.execution_path(), 'debug',
                              'autoserv.DEBUG')
        destination = os.path.join(
                self.queue_entry.execution_path(), log_name)

        self.monitor.try_copy_to_results_repository(
                source, destination_path=destination)


    def epilog(self):
        super(PreJobTask, self).epilog()

        if self.success:
            return

        self._copy_to_results_repository()

        if self.host.protection == host_protections.Protection.DO_NOT_VERIFY:
            return

        if self.queue_entry:
            self.queue_entry.requeue()

            if models.SpecialTask.objects.filter(
                    task=models.SpecialTask.Task.REPAIR,
                    queue_entry__id=self.queue_entry.id):
                self.host.set_status(models.Host.Status.REPAIR_FAILED)
                self._fail_queue_entry()
                return

            queue_entry = models.HostQueueEntry(id=self.queue_entry.id)
        else:
            queue_entry = None

        models.SpecialTask.objects.create(
                host=models.Host(id=self.host.id),
                task=models.SpecialTask.Task.REPAIR,
                queue_entry=queue_entry)


class VerifyTask(PreJobTask):
    TASK_TYPE = models.SpecialTask.Task.VERIFY


    def __init__(self, task, recover_run_monitor=None):
        super(VerifyTask, self).__init__(
                task, ['-v'], recover_run_monitor=recover_run_monitor)

        self._set_ids(host=self.host, queue_entries=[self.queue_entry])


    def prolog(self):
        super(VerifyTask, self).prolog()

        logging.info("starting verify on %s", self.host.hostname)
        if self.queue_entry:
            self.queue_entry.set_status(models.HostQueueEntry.Status.VERIFYING)
        self.host.set_status(models.Host.Status.VERIFYING)

        # Delete any other queued verifies for this host.  One verify will do
        # and there's no need to keep records of other requests.
        queued_verifies = models.SpecialTask.objects.filter(
            host__id=self.host.id,
            task=models.SpecialTask.Task.VERIFY,
            is_active=False, is_complete=False)
        queued_verifies = queued_verifies.exclude(id=self.task.id)
        queued_verifies.delete()


    def epilog(self):
        super(VerifyTask, self).epilog()
        if self.success:
            if self.queue_entry:
                self.queue_entry.on_pending()
            else:
                self.host.set_status(models.Host.Status.READY)


class CleanupHostsMixin(object):
    def _reboot_hosts(self, job, queue_entries, final_success,
                      num_tests_failed):
        reboot_after = job.reboot_after
        do_reboot = (
                # always reboot after aborted jobs
                self._final_status == models.HostQueueEntry.Status.ABORTED
                or reboot_after == models.RebootAfter.ALWAYS
                or (reboot_after == models.RebootAfter.IF_ALL_TESTS_PASSED
                    and final_success and num_tests_failed == 0))

        for queue_entry in queue_entries:
            if do_reboot:
                # don't pass the queue entry to the CleanupTask. if the cleanup
                # fails, the job doesn't care -- it's over.
                models.SpecialTask.objects.create(
                        host=models.Host(id=queue_entry.host.id),
                        task=models.SpecialTask.Task.CLEANUP)
            else:
                queue_entry.host.set_status(models.Host.Status.READY)


class QueueTask(AgentTask, TaskWithJobKeyvals, CleanupHostsMixin):
    def __init__(self, job, queue_entries, cmd=None, recover_run_monitor=None):
        self.job = job
        self.queue_entries = queue_entries
        self.group_name = queue_entries[0].get_group_name()
        super(QueueTask, self).__init__(
                cmd, self._execution_path(),
                recover_run_monitor=recover_run_monitor)
        self._set_ids(queue_entries=queue_entries)


    def _keyval_path(self):
        return os.path.join(self._execution_path(), self._KEYVAL_FILE)


    def _execution_path(self):
        return self.queue_entries[0].execution_path()


    def prolog(self):
        for entry in self.queue_entries:
            if entry.status not in (models.HostQueueEntry.Status.STARTING,
                                    models.HostQueueEntry.Status.RUNNING):
                raise SchedulerError('Queue task attempting to start '
                                     'entry with invalid status %s: %s'
                                     % (entry.status, entry))
            if entry.host.status not in (models.Host.Status.PENDING,
                                         models.Host.Status.RUNNING):
                raise SchedulerError('Queue task attempting to start on queue '
                                     'entry with invalid host status %s: %s'
                                     % (entry.host.status, entry))

        queued_key, queued_time = self._job_queued_keyval(self.job)
        keyval_dict = {queued_key: queued_time}
        if self.group_name:
            keyval_dict['host_group_name'] = self.group_name
        self._write_keyvals_before_job(keyval_dict)
        for queue_entry in self.queue_entries:
            self._write_host_keyvals(queue_entry.host)
            queue_entry.set_status(models.HostQueueEntry.Status.RUNNING)
            queue_entry.update_field('started_on', datetime.datetime.now())
            queue_entry.host.set_status(models.Host.Status.RUNNING)
            queue_entry.host.update_field('dirty', 1)
        if self.job.synch_count == 1 and len(self.queue_entries) == 1:
            # TODO(gps): Remove this if nothing needs it anymore.
            # A potential user is: tko/parser
            self.job.write_to_machines_file(self.queue_entries[0])


    def _write_lost_process_error_file(self):
        error_file_path = os.path.join(self._execution_path(), 'job_failure')
        _drone_manager.write_lines_to_file(error_file_path,
                                           [_LOST_PROCESS_ERROR])


    def _finish_task(self):
        if not self.monitor:
            return

        self._write_job_finished()

        if self.monitor.lost_process:
            self._write_lost_process_error_file()

        for queue_entry in self.queue_entries:
            queue_entry.set_status(models.HostQueueEntry.Status.GATHERING)


    def _write_status_comment(self, comment):
        _drone_manager.write_lines_to_file(
            os.path.join(self._execution_path(), 'status.log'),
            ['INFO\t----\t----\t' + comment],
            paired_with_process=self.monitor.get_process())


    def _log_abort(self):
        if not self.monitor or not self.monitor.has_process():
            return

        # build up sets of all the aborted_by and aborted_on values
        aborted_by, aborted_on = set(), set()
        for queue_entry in self.queue_entries:
            if queue_entry.aborted_by:
                aborted_by.add(queue_entry.aborted_by)
                t = int(time.mktime(queue_entry.aborted_on.timetuple()))
                aborted_on.add(t)

        # extract some actual, unique aborted by value and write it out
        assert len(aborted_by) <= 1
        if len(aborted_by) == 1:
            aborted_by_value = aborted_by.pop()
            aborted_on_value = max(aborted_on)
        else:
            aborted_by_value = 'autotest_system'
            aborted_on_value = int(time.time())

        self._write_keyval_after_job("aborted_by", aborted_by_value)
        self._write_keyval_after_job("aborted_on", aborted_on_value)

        aborted_on_string = str(datetime.datetime.fromtimestamp(
            aborted_on_value))
        self._write_status_comment('Job aborted by %s on %s' %
                                   (aborted_by_value, aborted_on_string))


    def abort(self):
        super(QueueTask, self).abort()
        self._log_abort()
        self._finish_task()


    def epilog(self):
        super(QueueTask, self).epilog()
        self._finish_task()
        logging.info("queue_task finished with success=%s", self.success)


class PostJobTask(AgentTask):
    def __init__(self, queue_entries, pidfile_name, logfile_name,
                 recover_run_monitor=None):
        self._queue_entries = queue_entries
        self._pidfile_name = pidfile_name

        self._execution_path = self._get_consistent_execution_path(
                queue_entries)
        self._results_dir = _drone_manager.absolute_path(self._execution_path)
        self._autoserv_monitor = PidfileRunMonitor()
        self._autoserv_monitor.attach_to_existing_process(self._execution_path)
        self._paired_with_pidfile = self._autoserv_monitor.pidfile_id

        if _testing_mode:
            command = 'true'
        else:
            command = self._generate_command(self._results_dir)

        super(PostJobTask, self).__init__(
                cmd=command, working_directory=self._execution_path,
                recover_run_monitor=recover_run_monitor)

        self.log_file = os.path.join(self._execution_path, logfile_name)
        self._final_status = self._determine_final_status()


    def _generate_command(self, results_dir):
        raise NotImplementedError('Subclasses must override this')


    def _job_was_aborted(self):
        was_aborted = None
        for queue_entry in self._queue_entries:
            queue_entry.update_from_database()
            if was_aborted is None: # first queue entry
                was_aborted = bool(queue_entry.aborted)
            elif was_aborted != bool(queue_entry.aborted): # subsequent entries
                email_manager.manager.enqueue_notify_email(
                    'Inconsistent abort state',
                    'Queue entries have inconsistent abort state: ' +
                    ', '.join('%s (%s)' % (queue_entry, queue_entry.aborted)))
                # don't crash here, just assume true
                return True
        return was_aborted


    def _determine_final_status(self):
        if self._job_was_aborted():
            return models.HostQueueEntry.Status.ABORTED

        # we'll use a PidfileRunMonitor to read the autoserv exit status
        if self._autoserv_monitor.exit_code() == 0:
            return models.HostQueueEntry.Status.COMPLETED
        return models.HostQueueEntry.Status.FAILED


    def run(self):
        # Make sure we actually have results to work with.
        # This should never happen in normal operation.
        if not self._autoserv_monitor.has_process():
            email_manager.manager.enqueue_notify_email(
                    'No results in post-job task',
                    'No results in post-job task at %s' %
                    self._autoserv_monitor.pidfile_id)
            self.finished(False)
            return

        super(PostJobTask, self).run(
            pidfile_name=self._pidfile_name,
            paired_with_pidfile=self._paired_with_pidfile)


    def _set_all_statuses(self, status):
        for queue_entry in self._queue_entries:
            queue_entry.set_status(status)


    def abort(self):
        # override AgentTask.abort() to avoid killing the process and ending
        # the task.  post-job tasks continue when the job is aborted.
        pass


class GatherLogsTask(PostJobTask, CleanupHostsMixin):
    """
    Task responsible for
    * gathering uncollected logs (if Autoserv crashed hard or was killed)
    * copying logs to the results repository
    * spawning CleanupTasks for hosts, if necessary
    * spawning a FinalReparseTask for the job
    """
    def __init__(self, job, queue_entries, recover_run_monitor=None):
        self._job = job
        super(GatherLogsTask, self).__init__(
            queue_entries, pidfile_name=_CRASHINFO_PID_FILE,
            logfile_name='.collect_crashinfo.log',
            recover_run_monitor=recover_run_monitor)
        self._set_ids(queue_entries=queue_entries)


    def _generate_command(self, results_dir):
        host_list = ','.join(queue_entry.host.hostname
                             for queue_entry in self._queue_entries)
        return [_autoserv_path , '-p', '--collect-crashinfo', '-m', host_list,
                '-r', results_dir]


    def prolog(self):
        for queue_entry in self._queue_entries:
            if queue_entry.status != models.HostQueueEntry.Status.GATHERING:
                raise SchedulerError('Gather task attempting to start on '
                                     'non-gathering entry: %s' % queue_entry)
            if queue_entry.host.status != models.Host.Status.RUNNING:
                raise SchedulerError('Gather task attempting to start on queue '
                                     'entry with non-running host status %s: %s'
                                     % (queue_entry.host.status, queue_entry))

        super(GatherLogsTask, self).prolog()


    def epilog(self):
        super(GatherLogsTask, self).epilog()

        self._copy_and_parse_results(self._queue_entries,
                                     use_monitor=self._autoserv_monitor)

        if self._autoserv_monitor.has_process():
            final_success = (self._final_status ==
                             models.HostQueueEntry.Status.COMPLETED)
            num_tests_failed = self._autoserv_monitor.num_tests_failed()
        else:
            final_success = False
            num_tests_failed = 0

        self._reboot_hosts(self._job, self._queue_entries, final_success,
                           num_tests_failed)


    def run(self):
        autoserv_exit_code = self._autoserv_monitor.exit_code()
        # only run if Autoserv exited due to some signal. if we have no exit
        # code, assume something bad (and signal-like) happened.
        if autoserv_exit_code is None or os.WIFSIGNALED(autoserv_exit_code):
            super(GatherLogsTask, self).run()
        else:
            self.finished(True)


class CleanupTask(PreJobTask):
    TASK_TYPE = models.SpecialTask.Task.CLEANUP


    def __init__(self, task, recover_run_monitor=None):
        super(CleanupTask, self).__init__(
                task, ['--cleanup'], recover_run_monitor=recover_run_monitor)

        self._set_ids(host=self.host, queue_entries=[self.queue_entry])


    def prolog(self):
        super(CleanupTask, self).prolog()
        logging.info("starting cleanup task for host: %s", self.host.hostname)
        self.host.set_status(models.Host.Status.CLEANING)
        if self.queue_entry:
            self.queue_entry.set_status(models.HostQueueEntry.Status.VERIFYING)


    def _finish_epilog(self):
        if not self.queue_entry:
            return

        if self.host.protection == host_protections.Protection.DO_NOT_VERIFY:
            self.queue_entry.on_pending()
        elif self.success:
            if self.queue_entry.job.run_verify:
                entry = models.HostQueueEntry(id=self.queue_entry.id)
                models.SpecialTask.objects.create(
                        host=models.Host(id=self.host.id),
                        queue_entry=entry,
                        task=models.SpecialTask.Task.VERIFY)
            else:
                self.queue_entry.on_pending()


    def epilog(self):
        super(CleanupTask, self).epilog()

        if self.success:
            self.host.update_field('dirty', 0)
            self.host.set_status(models.Host.Status.READY)

        self._finish_epilog()


class FinalReparseTask(PostJobTask):
    _num_running_parses = 0

    def __init__(self, queue_entries, recover_run_monitor=None):
        super(FinalReparseTask, self).__init__(
                queue_entries, pidfile_name=_PARSER_PID_FILE,
                logfile_name='.parse.log',
                recover_run_monitor=recover_run_monitor)
        # don't use _set_ids, since we don't want to set the host_ids
        self.queue_entry_ids = [entry.id for entry in queue_entries]
        self._parse_started = self.started


    @classmethod
    def _increment_running_parses(cls):
        cls._num_running_parses += 1


    @classmethod
    def _decrement_running_parses(cls):
        cls._num_running_parses -= 1


    @classmethod
    def _can_run_new_parse(cls):
        return (cls._num_running_parses <
                scheduler_config.config.max_parse_processes)


    def prolog(self):
        for queue_entry in self._queue_entries:
            if queue_entry.status != models.HostQueueEntry.Status.PARSING:
                raise SchedulerError('Parse task attempting to start on '
                                     'non-parsing entry: %s' % queue_entry)

        super(FinalReparseTask, self).prolog()


    def epilog(self):
        super(FinalReparseTask, self).epilog()
        self._set_all_statuses(self._final_status)


    def _generate_command(self, results_dir):
        return [_parser_path, '--write-pidfile', '-l', '2', '-r', '-o', '-P',
                results_dir]


    def tick(self):
        # override tick to keep trying to start until the parse count goes down
        # and we can, at which point we revert to default behavior
        if self._parse_started:
            super(FinalReparseTask, self).tick()
        else:
            self._try_starting_parse()


    def run(self):
        # override run() to not actually run unless we can
        self._try_starting_parse()


    def _try_starting_parse(self):
        if not self._can_run_new_parse():
            return

        # actually run the parse command
        super(FinalReparseTask, self).run()

        self._increment_running_parses()
        self._parse_started = True


    def finished(self, success):
        super(FinalReparseTask, self).finished(success)
        if self._parse_started:
            self._decrement_running_parses()


class DBError(Exception):
    """Raised by the DBObject constructor when its select fails."""


class DBObject(object):
    """A miniature object relational model for the database."""

    # Subclasses MUST override these:
    _table_name = ''
    _fields = ()

    # A mapping from (type, id) to the instance of the object for that
    # particular id.  This prevents us from creating new Job() and Host()
    # instances for every HostQueueEntry object that we instantiate as
    # multiple HQEs often share the same Job.
    _instances_by_type_and_id = weakref.WeakValueDictionary()
    _initialized = False


    def __new__(cls, id=None, **kwargs):
        """
        Look to see if we already have an instance for this particular type
        and id.  If so, use it instead of creating a duplicate instance.
        """
        if id is not None:
            instance = cls._instances_by_type_and_id.get((cls, id))
            if instance:
                return instance
        return super(DBObject, cls).__new__(cls, id=id, **kwargs)


    def __init__(self, id=None, row=None, new_record=False, always_query=True):
        assert bool(id) or bool(row)
        if id is not None and row is not None:
            assert id == row[0]
        assert self._table_name, '_table_name must be defined in your class'
        assert self._fields, '_fields must be defined in your class'
        if not new_record:
            if self._initialized and not always_query:
                return  # We've already been initialized.
            if id is None:
                id = row[0]
            # Tell future constructors to use us instead of re-querying while
            # this instance is still around.
            self._instances_by_type_and_id[(type(self), id)] = self

        self.__table = self._table_name

        self.__new_record = new_record

        if row is None:
            row = self._fetch_row_from_db(id)

        if self._initialized:
            differences = self._compare_fields_in_row(row)
            if differences:
                logging.warn(
                    'initialized %s %s instance requery is updating: %s',
                    type(self), self.id, differences)
        self._update_fields_from_row(row)
        self._initialized = True


    @classmethod
    def _clear_instance_cache(cls):
        """Used for testing, clear the internal instance cache."""
        cls._instances_by_type_and_id.clear()


    def _fetch_row_from_db(self, row_id):
        sql = 'SELECT * FROM %s WHERE ID=%%s' % self.__table
        rows = _db.execute(sql, (row_id,))
        if not rows:
            raise DBError("row not found (table=%s, row id=%s)"
                          % (self.__table, row_id))
        return rows[0]


    def _assert_row_length(self, row):
        assert len(row) == len(self._fields), (
            "table = %s, row = %s/%d, fields = %s/%d" % (
            self.__table, row, len(row), self._fields, len(self._fields)))


    def _compare_fields_in_row(self, row):
        """
        Given a row as returned by a SELECT query, compare it to our existing
        in memory fields.

        @param row - A sequence of values corresponding to fields named in
                The class attribute _fields.

        @returns A dictionary listing the differences keyed by field name
                containing tuples of (current_value, row_value).
        """
        self._assert_row_length(row)
        differences = {}
        for field, row_value in itertools.izip(self._fields, row):
            current_value = getattr(self, field)
            if current_value != row_value:
                differences[field] = (current_value, row_value)
        return differences


    def _update_fields_from_row(self, row):
        """
        Update our field attributes using a single row returned by SELECT.

        @param row - A sequence of values corresponding to fields named in
                the class fields list.
        """
        self._assert_row_length(row)

        self._valid_fields = set()
        for field, value in itertools.izip(self._fields, row):
            setattr(self, field, value)
            self._valid_fields.add(field)

        self._valid_fields.remove('id')


    def update_from_database(self):
        assert self.id is not None
        row = self._fetch_row_from_db(self.id)
        self._update_fields_from_row(row)


    def count(self, where, table = None):
        if not table:
            table = self.__table

        rows = _db.execute("""
                SELECT count(*) FROM %s
                WHERE %s
        """ % (table, where))

        assert len(rows) == 1

        return int(rows[0][0])


    def update_field(self, field, value):
        assert field in self._valid_fields

        if getattr(self, field) == value:
            return

        query = "UPDATE %s SET %s = %%s WHERE id = %%s" % (self.__table, field)
        _db.execute(query, (value, self.id))

        setattr(self, field, value)


    def save(self):
        if self.__new_record:
            keys = self._fields[1:] # avoid id
            columns = ','.join([str(key) for key in keys])
            values = []
            for key in keys:
                value = getattr(self, key)
                if value is None:
                    values.append('NULL')
                else:
                    values.append('"%s"' % value)
            values_str = ','.join(values)
            query = ('INSERT INTO %s (%s) VALUES (%s)' %
                     (self.__table, columns, values_str))
            _db.execute(query)
            # Update our id to the one the database just assigned to us.
            self.id = _db.execute('SELECT LAST_INSERT_ID()')[0][0]


    def delete(self):
        self._instances_by_type_and_id.pop((type(self), id), None)
        self._initialized = False
        self._valid_fields.clear()
        query = 'DELETE FROM %s WHERE id=%%s' % self.__table
        _db.execute(query, (self.id,))


    @staticmethod
    def _prefix_with(string, prefix):
        if string:
            string = prefix + string
        return string


    @classmethod
    def fetch(cls, where='', params=(), joins='', order_by=''):
        """
        Construct instances of our class based on the given database query.

        @yields One class instance for each row fetched.
        """
        order_by = cls._prefix_with(order_by, 'ORDER BY ')
        where = cls._prefix_with(where, 'WHERE ')
        query = ('SELECT %(table)s.* FROM %(table)s %(joins)s '
                 '%(where)s %(order_by)s' % {'table' : cls._table_name,
                                             'joins' : joins,
                                             'where' : where,
                                             'order_by' : order_by})
        rows = _db.execute(query, params)
        return [cls(id=row[0], row=row) for row in rows]


class IneligibleHostQueue(DBObject):
    _table_name = 'ineligible_host_queues'
    _fields = ('id', 'job_id', 'host_id')


class AtomicGroup(DBObject):
    _table_name = 'atomic_groups'
    _fields = ('id', 'name', 'description', 'max_number_of_machines',
               'invalid')


class Label(DBObject):
    _table_name = 'labels'
    _fields = ('id', 'name', 'kernel_config', 'platform', 'invalid',
               'only_if_needed', 'atomic_group_id')


    def __repr__(self):
        return 'Label(name=%r, id=%d, atomic_group_id=%r)' % (
                self.name, self.id, self.atomic_group_id)


class Host(DBObject):
    _table_name = 'hosts'
    _fields = ('id', 'hostname', 'locked', 'synch_id', 'status',
               'invalid', 'protection', 'locked_by_id', 'lock_time', 'dirty')


    def set_status(self,status):
        logging.info('%s -> %s', self.hostname, status)
        self.update_field('status',status)


    def platform_and_labels(self):
        """
        Returns a tuple (platform_name, list_of_all_label_names).
        """
        rows = _db.execute("""
                SELECT labels.name, labels.platform
                FROM labels
                INNER JOIN hosts_labels ON labels.id = hosts_labels.label_id
                WHERE hosts_labels.host_id = %s
                ORDER BY labels.name
                """, (self.id,))
        platform = None
        all_labels = []
        for label_name, is_platform in rows:
            if is_platform:
                platform = label_name
            all_labels.append(label_name)
        return platform, all_labels


    _ALPHANUM_HOST_RE = re.compile(r'^([a-z-]+)(\d+)$', re.IGNORECASE)


    @classmethod
    def cmp_for_sort(cls, a, b):
        """
        A comparison function for sorting Host objects by hostname.

        This strips any trailing numeric digits, ignores leading 0s and
        compares hostnames by the leading name and the trailing digits as a
        number.  If both hostnames do not match this pattern, they are simply
        compared as lower case strings.

        Example of how hostnames will be sorted:

          alice, host1, host2, host09, host010, host10, host11, yolkfolk

        This hopefully satisfy most people's hostname sorting needs regardless
        of their exact naming schemes.  Nobody sane should have both a host10
        and host010 (but the algorithm works regardless).
        """
        lower_a = a.hostname.lower()
        lower_b = b.hostname.lower()
        match_a = cls._ALPHANUM_HOST_RE.match(lower_a)
        match_b = cls._ALPHANUM_HOST_RE.match(lower_b)
        if match_a and match_b:
            name_a, number_a_str = match_a.groups()
            name_b, number_b_str = match_b.groups()
            number_a = int(number_a_str.lstrip('0'))
            number_b = int(number_b_str.lstrip('0'))
            result = cmp((name_a, number_a), (name_b, number_b))
            if result == 0 and lower_a != lower_b:
                # If they compared equal above but the lower case names are
                # indeed different, don't report equality.  abc012 != abc12.
                return cmp(lower_a, lower_b)
            return result
        else:
            return cmp(lower_a, lower_b)


class HostQueueEntry(DBObject):
    _table_name = 'host_queue_entries'
    _fields = ('id', 'job_id', 'host_id', 'status', 'meta_host',
               'active', 'complete', 'deleted', 'execution_subdir',
               'atomic_group_id', 'aborted', 'started_on')


    def __init__(self, id=None, row=None, **kwargs):
        assert id or row
        super(HostQueueEntry, self).__init__(id=id, row=row, **kwargs)
        self.job = Job(self.job_id)

        if self.host_id:
            self.host = Host(self.host_id)
        else:
            self.host = None

        if self.atomic_group_id:
            self.atomic_group = AtomicGroup(self.atomic_group_id,
                                            always_query=False)
        else:
            self.atomic_group = None

        self.queue_log_path = os.path.join(self.job.tag(),
                                           'queue.log.' + str(self.id))


    @classmethod
    def clone(cls, template):
        """
        Creates a new row using the values from a template instance.

        The new instance will not exist in the database or have a valid
        id attribute until its save() method is called.
        """
        assert isinstance(template, cls)
        new_row = [getattr(template, field) for field in cls._fields]
        clone = cls(row=new_row, new_record=True)
        clone.id = None
        return clone


    def _view_job_url(self):
        return "%s#tab_id=view_job&object_id=%s" % (_base_url, self.job.id)


    def get_labels(self):
        """
        Get all labels associated with this host queue entry (either via the
        meta_host or as a job dependency label).  The labels yielded are not
        guaranteed to be unique.

        @yields Label instances associated with this host_queue_entry.
        """
        if self.meta_host:
            yield Label(id=self.meta_host, always_query=False)
        labels = Label.fetch(
                joins="JOIN jobs_dependency_labels AS deps "
                      "ON (labels.id = deps.label_id)",
                where="deps.job_id = %d" % self.job.id)
        for label in labels:
            yield label


    def set_host(self, host):
        if host:
            self.queue_log_record('Assigning host ' + host.hostname)
            self.update_field('host_id', host.id)
            self.update_field('active', True)
            self.block_host(host.id)
        else:
            self.queue_log_record('Releasing host')
            self.unblock_host(self.host.id)
            self.update_field('host_id', None)

        self.host = host


    def get_host(self):
        return self.host


    def queue_log_record(self, log_line):
        now = str(datetime.datetime.now())
        _drone_manager.write_lines_to_file(self.queue_log_path,
                                           [now + ' ' + log_line])


    def block_host(self, host_id):
        logging.info("creating block %s/%s", self.job.id, host_id)
        row = [0, self.job.id, host_id]
        block = IneligibleHostQueue(row=row, new_record=True)
        block.save()


    def unblock_host(self, host_id):
        logging.info("removing block %s/%s", self.job.id, host_id)
        blocks = IneligibleHostQueue.fetch(
            'job_id=%d and host_id=%d' % (self.job.id, host_id))
        for block in blocks:
            block.delete()


    def set_execution_subdir(self, subdir=None):
        if subdir is None:
            assert self.get_host()
            subdir = self.get_host().hostname
        self.update_field('execution_subdir', subdir)


    def _get_hostname(self):
        if self.host:
            return self.host.hostname
        return 'no host'


    def __str__(self):
        flags = []
        if self.active:
            flags.append('active')
        if self.complete:
            flags.append('complete')
        if self.deleted:
            flags.append('deleted')
        if self.aborted:
            flags.append('aborted')
        flags_str = ','.join(flags)
        if flags_str:
            flags_str = ' [%s]' % flags_str
        return "%s/%d (%d) %s%s" % (self._get_hostname(), self.job.id, self.id,
                                    self.status, flags_str)


    def set_status(self, status):
        self.update_field('status', status)

        logging.info("%s -> %s", self, self.status)

        if status in (models.HostQueueEntry.Status.QUEUED,
                      models.HostQueueEntry.Status.PARSING):
            self.update_field('complete', False)
            self.update_field('active', False)

        if status in (models.HostQueueEntry.Status.PENDING,
                      models.HostQueueEntry.Status.RUNNING,
                      models.HostQueueEntry.Status.VERIFYING,
                      models.HostQueueEntry.Status.STARTING,
                      models.HostQueueEntry.Status.GATHERING):
            self.update_field('complete', False)
            self.update_field('active', True)

        if status in (models.HostQueueEntry.Status.FAILED,
                      models.HostQueueEntry.Status.COMPLETED,
                      models.HostQueueEntry.Status.STOPPED,
                      models.HostQueueEntry.Status.ABORTED):
            self.update_field('complete', True)
            self.update_field('active', False)

        should_email_status = (status.lower() in _notify_email_statuses or
                               'all' in _notify_email_statuses)
        if should_email_status:
            self._email_on_status(status)

        self._email_on_job_complete()


    def _email_on_status(self, status):
        hostname = self._get_hostname()

        subject = 'Autotest: Job ID: %s "%s" Host: %s %s' % (
                self.job.id, self.job.name, hostname, status)
        body = "Job ID: %s\nJob Name: %s\nHost: %s\nStatus: %s\n%s\n" % (
                self.job.id, self.job.name, hostname, status,
                self._view_job_url())
        email_manager.manager.send_email(self.job.email_list, subject, body)


    def _email_on_job_complete(self):
        if not self.job.is_finished():
            return

        summary_text = []
        hosts_queue = HostQueueEntry.fetch('job_id = %s' % self.job.id)
        for queue_entry in hosts_queue:
            summary_text.append("Host: %s Status: %s" %
                                (queue_entry._get_hostname(),
                                 queue_entry.status))

        summary_text = "\n".join(summary_text)
        status_counts = models.Job.objects.get_status_counts(
                [self.job.id])[self.job.id]
        status = ', '.join('%d %s' % (count, status) for status, count
                    in status_counts.iteritems())

        subject = 'Autotest: Job ID: %s "%s" %s' % (
                self.job.id, self.job.name, status)
        body = "Job ID: %s\nJob Name: %s\nStatus: %s\n%s\nSummary:\n%s" % (
                self.job.id, self.job.name, status,  self._view_job_url(),
                summary_text)
        email_manager.manager.send_email(self.job.email_list, subject, body)


    def schedule_pre_job_tasks(self, assigned_host=None):
        if self.meta_host is not None or self.atomic_group:
            assert assigned_host
            # ensure results dir exists for the queue log
            if self.host_id is None:
                self.set_host(assigned_host)
            else:
                assert assigned_host.id == self.host_id

        logging.info("%s/%s/%s scheduled on %s, status=%s",
                     self.job.name, self.meta_host, self.atomic_group_id,
                     self.host.hostname, self.status)

        self._do_schedule_pre_job_tasks()


    def _do_schedule_pre_job_tasks(self):
        # Every host goes thru the Verifying stage (which may or may not
        # actually do anything as determined by get_pre_job_tasks).
        self.set_status(models.HostQueueEntry.Status.VERIFYING)
        self.job.schedule_pre_job_tasks(queue_entry=self)


    def requeue(self):
        assert self.host
        self.set_status(models.HostQueueEntry.Status.QUEUED)
        self.update_field('started_on', None)
        # verify/cleanup failure sets the execution subdir, so reset it here
        self.set_execution_subdir('')
        if self.meta_host:
            self.set_host(None)


    def handle_host_failure(self):
        """\
        Called when this queue entry's host has failed verification and
        repair.
        """
        assert not self.meta_host
        self.set_status(models.HostQueueEntry.Status.FAILED)
        self.job.stop_if_necessary()


    @property
    def aborted_by(self):
        self._load_abort_info()
        return self._aborted_by


    @property
    def aborted_on(self):
        self._load_abort_info()
        return self._aborted_on


    def _load_abort_info(self):
        """ Fetch info about who aborted the job. """
        if hasattr(self, "_aborted_by"):
            return
        rows = _db.execute("""
                SELECT users.login, aborted_host_queue_entries.aborted_on
                FROM aborted_host_queue_entries
                INNER JOIN users
                ON users.id = aborted_host_queue_entries.aborted_by_id
                WHERE aborted_host_queue_entries.queue_entry_id = %s
                """, (self.id,))
        if rows:
            self._aborted_by, self._aborted_on = rows[0]
        else:
            self._aborted_by = self._aborted_on = None


    def on_pending(self):
        """
        Called when an entry in a synchronous job has passed verify.  If the
        job is ready to run, sets the entries to STARTING. Otherwise, it leaves
        them in PENDING.
        """
        self.set_status(models.HostQueueEntry.Status.PENDING)
        self.host.set_status(models.Host.Status.PENDING)

        # Some debug code here: sends an email if an asynchronous job does not
        # immediately enter Starting.
        # TODO: Remove this once we figure out why asynchronous jobs are getting
        # stuck in Pending.
        self.job.run_if_ready(queue_entry=self)
        if (self.job.synch_count == 1 and
                self.status == models.HostQueueEntry.Status.PENDING):
            subject = 'Job %s (id %s)' % (self.job.name, self.job.id)
            message = 'Asynchronous job stuck in Pending'
            email_manager.manager.enqueue_notify_email(subject, message)


    def abort(self, dispatcher):
        assert self.aborted and not self.complete

        Status = models.HostQueueEntry.Status
        if self.status in (Status.GATHERING, Status.PARSING):
            # do nothing; post-job tasks will finish and then mark this entry
            # with status "Aborted" and take care of the host
            return

        if self.status in (Status.STARTING, Status.PENDING, Status.RUNNING):
            assert not dispatcher.get_agents_for_entry(self)
            self.host.set_status(models.Host.Status.READY)
        elif self.status == Status.VERIFYING:
            models.SpecialTask.objects.create(
                    task=models.SpecialTask.Task.CLEANUP,
                    host=models.Host(id=self.host.id))

        self.set_status(Status.ABORTED)


    def get_group_name(self):
        atomic_group = self.atomic_group
        if not atomic_group:
            return ''

        # Look at any meta_host and dependency labels and pick the first
        # one that also specifies this atomic group.  Use that label name
        # as the group name if possible (it is more specific).
        for label in self.get_labels():
            if label.atomic_group_id:
                assert label.atomic_group_id == atomic_group.id
                return label.name
        return atomic_group.name


    def execution_tag(self):
        assert self.execution_subdir
        return "%s/%s" % (self.job.tag(), self.execution_subdir)


    def execution_path(self):
        return self.execution_tag()


class Job(DBObject):
    _table_name = 'jobs'
    _fields = ('id', 'owner', 'name', 'priority', 'control_file',
               'control_type', 'created_on', 'synch_count', 'timeout',
               'run_verify', 'email_list', 'reboot_before', 'reboot_after',
               'parse_failed_repair', 'max_runtime_hrs')

    # This does not need to be a column in the DB.  The delays are likely to
    # be configured short.  If the scheduler is stopped and restarted in
    # the middle of a job's delay cycle, the delay cycle will either be
    # repeated or skipped depending on the number of Pending machines found
    # when the restarted scheduler recovers to track it.  Not a problem.
    #
    # A reference to the DelayedCallTask that will wake up the job should
    # no other HQEs change state in time.  Its end_time attribute is used
    # by our run_with_ready_delay() method to determine if the wait is over.
    _delay_ready_task = None

    # TODO(gps): On scheduler start/recovery we need to call HQE.on_pending() on
    # all status='Pending' atomic group HQEs incase a delay was running when the
    # scheduler was restarted and no more hosts ever successfully exit Verify.

    def __init__(self, id=None, row=None, **kwargs):
        assert id or row
        super(Job, self).__init__(id=id, row=row, **kwargs)


    def is_server_job(self):
        return self.control_type != 2


    def tag(self):
        return "%s-%s" % (self.id, self.owner)


    def get_host_queue_entries(self):
        rows = _db.execute("""
                SELECT * FROM host_queue_entries
                WHERE job_id= %s
        """, (self.id,))
        entries = [HostQueueEntry(row=i) for i in rows]

        assert len(entries)>0

        return entries


    def set_status(self, status, update_queues=False):
        self.update_field('status',status)

        if update_queues:
            for queue_entry in self.get_host_queue_entries():
                queue_entry.set_status(status)


    def _atomic_and_has_started(self):
        """
        @returns True if any of the HostQueueEntries associated with this job
        have entered the Status.STARTING state or beyond.
        """
        atomic_entries = models.HostQueueEntry.objects.filter(
                job=self.id, atomic_group__isnull=False)
        if atomic_entries.count() <= 0:
            return False

        # These states may *only* be reached if Job.run() has been called.
        started_statuses = (models.HostQueueEntry.Status.STARTING,
                            models.HostQueueEntry.Status.RUNNING,
                            models.HostQueueEntry.Status.COMPLETED)

        started_entries = atomic_entries.filter(status__in=started_statuses)
        return started_entries.count() > 0


    def _hosts_assigned_count(self):
        """The number of HostQueueEntries assigned a Host for this job."""
        entries = models.HostQueueEntry.objects.filter(job=self.id,
                                                       host__isnull=False)
        return entries.count()


    def _pending_count(self):
        """The number of HostQueueEntries for this job in the Pending state."""
        pending_entries = models.HostQueueEntry.objects.filter(
                job=self.id, status=models.HostQueueEntry.Status.PENDING)
        return pending_entries.count()


    def is_ready(self):
        # NOTE: Atomic group jobs stop reporting ready after they have been
        # started to avoid launching multiple copies of one atomic job.
        # Only possible if synch_count is less than than half the number of
        # machines in the atomic group.
        pending_count = self._pending_count()
        atomic_and_has_started = self._atomic_and_has_started()
        ready = (pending_count >= self.synch_count
                 and not self._atomic_and_has_started())

        if not ready:
            logging.info(
                    'Job %s not ready: %s pending, %s required '
                    '(Atomic and started: %s)',
                    self, pending_count, self.synch_count,
                    atomic_and_has_started)

        return ready


    def num_machines(self, clause = None):
        sql = "job_id=%s" % self.id
        if clause:
            sql += " AND (%s)" % clause
        return self.count(sql, table='host_queue_entries')


    def num_queued(self):
        return self.num_machines('not complete')


    def num_active(self):
        return self.num_machines('active')


    def num_complete(self):
        return self.num_machines('complete')


    def is_finished(self):
        return self.num_complete() == self.num_machines()


    def _not_yet_run_entries(self, include_verifying=True):
        statuses = [models.HostQueueEntry.Status.QUEUED,
                    models.HostQueueEntry.Status.PENDING]
        if include_verifying:
            statuses.append(models.HostQueueEntry.Status.VERIFYING)
        return models.HostQueueEntry.objects.filter(job=self.id,
                                                    status__in=statuses)


    def _stop_all_entries(self):
        entries_to_stop = self._not_yet_run_entries(
            include_verifying=False)
        for child_entry in entries_to_stop:
            assert not child_entry.complete, (
                '%s status=%s, active=%s, complete=%s' %
                (child_entry.id, child_entry.status, child_entry.active,
                 child_entry.complete))
            if child_entry.status == models.HostQueueEntry.Status.PENDING:
                child_entry.host.status = models.Host.Status.READY
                child_entry.host.save()
            child_entry.status = models.HostQueueEntry.Status.STOPPED
            child_entry.save()

    def stop_if_necessary(self):
        not_yet_run = self._not_yet_run_entries()
        if not_yet_run.count() < self.synch_count:
            self._stop_all_entries()


    def write_to_machines_file(self, queue_entry):
        hostname = queue_entry.get_host().hostname
        file_path = os.path.join(self.tag(), '.machines')
        _drone_manager.write_lines_to_file(file_path, [hostname])


    def _next_group_name(self, group_name=''):
        """@returns a directory name to use for the next host group results."""
        if group_name:
            # Sanitize for use as a pathname.
            group_name = group_name.replace(os.path.sep, '_')
            if group_name.startswith('.'):
                group_name = '_' + group_name[1:]
            # Add a separator between the group name and 'group%d'.
            group_name += '.'
        group_count_re = re.compile(r'%sgroup(\d+)' % re.escape(group_name))
        query = models.HostQueueEntry.objects.filter(
            job=self.id).values('execution_subdir').distinct()
        subdirs = (entry['execution_subdir'] for entry in query)
        group_matches = (group_count_re.match(subdir) for subdir in subdirs)
        ids = [int(match.group(1)) for match in group_matches if match]
        if ids:
            next_id = max(ids) + 1
        else:
            next_id = 0
        return '%sgroup%d' % (group_name, next_id)


    def _write_control_file(self, execution_path):
        control_path = _drone_manager.attach_file_to_execution(
                execution_path, self.control_file)
        return control_path


    def get_group_entries(self, queue_entry_from_group):
        execution_subdir = queue_entry_from_group.execution_subdir
        return list(HostQueueEntry.fetch(
            where='job_id=%s AND execution_subdir=%s',
            params=(self.id, execution_subdir)))


    def get_autoserv_params(self, queue_entries):
        assert queue_entries
        execution_path = queue_entries[0].execution_path()
        control_path = self._write_control_file(execution_path)
        hostnames = ','.join([entry.get_host().hostname
                              for entry in queue_entries])

        execution_tag = queue_entries[0].execution_tag()
        params = _autoserv_command_line(
            hostnames,
            ['-P', execution_tag, '-n',
             _drone_manager.absolute_path(control_path)],
            job=self, verbose=False)

        if not self.is_server_job():
            params.append('-c')

        return params


    def _should_run_cleanup(self, queue_entry):
        if self.reboot_before == models.RebootBefore.ALWAYS:
            return True
        elif self.reboot_before == models.RebootBefore.IF_DIRTY:
            return queue_entry.get_host().dirty
        return False


    def _should_run_verify(self, queue_entry):
        do_not_verify = (queue_entry.host.protection ==
                         host_protections.Protection.DO_NOT_VERIFY)
        if do_not_verify:
            return False
        return self.run_verify


    def schedule_pre_job_tasks(self, queue_entry):
        """
        Get a list of tasks to perform before the host_queue_entry
        may be used to run this Job (such as Cleanup & Verify).

        @returns A list of tasks to be done to the given queue_entry before
                it should be considered be ready to run this job.  The last
                task in the list calls HostQueueEntry.on_pending(), which
                continues the flow of the job.
        """
        if self._should_run_cleanup(queue_entry):
            task = models.SpecialTask.Task.CLEANUP
        elif self._should_run_verify(queue_entry):
            task = models.SpecialTask.Task.VERIFY
        else:
            queue_entry.on_pending()
            return

        models.SpecialTask.objects.create(
                host=models.Host(id=queue_entry.host_id),
                queue_entry=models.HostQueueEntry(id=queue_entry.id),
                task=task)


    def _assign_new_group(self, queue_entries, group_name=''):
        if len(queue_entries) == 1:
            group_subdir_name = queue_entries[0].get_host().hostname
        else:
            group_subdir_name = self._next_group_name(group_name)
            logging.info('Running synchronous job %d hosts %s as %s',
                self.id, [entry.host.hostname for entry in queue_entries],
                group_subdir_name)

        for queue_entry in queue_entries:
            queue_entry.set_execution_subdir(group_subdir_name)


    def _choose_group_to_run(self, include_queue_entry):
        """
        @returns A tuple containing a list of HostQueueEntry instances to be
                used to run this Job, a string group name to suggest giving
                to this job in the results database.
        """
        atomic_group = include_queue_entry.atomic_group
        chosen_entries = [include_queue_entry]
        if atomic_group:
            num_entries_wanted = atomic_group.max_number_of_machines
        else:
            num_entries_wanted = self.synch_count
        num_entries_wanted -= len(chosen_entries)

        if num_entries_wanted > 0:
            where_clause = 'job_id = %s AND status = "Pending" AND id != %s'
            pending_entries = list(HostQueueEntry.fetch(
                     where=where_clause,
                     params=(self.id, include_queue_entry.id)))

            # Sort the chosen hosts by hostname before slicing.
            def cmp_queue_entries_by_hostname(entry_a, entry_b):
                return Host.cmp_for_sort(entry_a.host, entry_b.host)
            pending_entries.sort(cmp=cmp_queue_entries_by_hostname)
            chosen_entries += pending_entries[:num_entries_wanted]

        # Sanity check.  We'll only ever be called if this can be met.
        if len(chosen_entries) < self.synch_count:
            message = ('job %s got less than %s chosen entries: %s' % (
                    self.id, self.synch_count, chosen_entries))
            logging.error(message)
            email_manager.manager.enqueue_notify_email(
                    'Job not started, too few chosen entries', message)
            return []

        group_name = include_queue_entry.get_group_name()

        self._assign_new_group(chosen_entries, group_name=group_name)
        return chosen_entries


    def run_if_ready(self, queue_entry):
        """
        @returns An Agent instance to ultimately run this job if enough hosts
                are ready for it to run.
        @returns None and potentially cleans up excess hosts if this Job
                is not ready to run.
        """
        if not self.is_ready():
            self.stop_if_necessary()
        elif queue_entry.atomic_group:
            self.run_with_ready_delay(queue_entry)
        else:
            self.run(queue_entry)


    def run_with_ready_delay(self, queue_entry):
        """
        Start a delay to wait for more hosts to enter Pending state before
        launching an atomic group job.  Once set, the a delay cannot be reset.

        @param queue_entry: The HostQueueEntry object to get atomic group
                info from and pass to run_if_ready when the delay is up.

        @returns An Agent to run the job as appropriate or None if a delay
                has already been set.
        """
        assert queue_entry.job_id == self.id
        assert queue_entry.atomic_group
        delay = scheduler_config.config.secs_to_wait_for_atomic_group_hosts
        pending_threshold = min(self._hosts_assigned_count(),
                                queue_entry.atomic_group.max_number_of_machines)
        over_max_threshold = (self._pending_count() >= pending_threshold)
        delay_expired = (self._delay_ready_task and
                         time.time() >= self._delay_ready_task.end_time)

        # Delay is disabled or we already have enough?  Do not wait to run.
        if not delay or over_max_threshold or delay_expired:
            self.run(queue_entry)
        else:
            queue_entry.set_status(models.HostQueueEntry.Status.WAITING)


    def schedule_delayed_callback_task(self, queue_entry):
        queue_entry.set_status(models.HostQueueEntry.Status.PENDING)

        if self._delay_ready_task:
            return None

        delay = scheduler_config.config.secs_to_wait_for_atomic_group_hosts

        def run_job_after_delay():
            logging.info('Job %s done waiting for extra hosts.', self.id)
            return self.run(queue_entry)

        logging.info('Job %s waiting up to %s seconds for more hosts.',
                     self.id, delay)
        self._delay_ready_task = DelayedCallTask(delay_seconds=delay,
                                                 callback=run_job_after_delay)
        return self._delay_ready_task


    def run(self, queue_entry):
        """
        @param queue_entry: The HostQueueEntry instance calling this method.
        """
        if queue_entry.atomic_group and self._atomic_and_has_started():
            logging.error('Job.run() called on running atomic Job %d '
                          'with HQE %s.', self.id, queue_entry)
            return
        queue_entries = self._choose_group_to_run(queue_entry)
        if queue_entries:
            self._finish_run(queue_entries)


    def _finish_run(self, queue_entries):
        for queue_entry in queue_entries:
            queue_entry.set_status(models.HostQueueEntry.Status.STARTING)
        if self._delay_ready_task:
            # Cancel any pending callback that would try to run again
            # as we are already running.
            self._delay_ready_task.abort()

    def __str__(self):
        return '%s-%s' % (self.id, self.owner)


if __name__ == '__main__':
    main()
