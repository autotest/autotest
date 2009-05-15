#!/usr/bin/python -u

"""
Autotest scheduler
"""


import datetime, errno, optparse, os, pwd, Queue, re, shutil, signal
import smtplib, socket, stat, subprocess, sys, tempfile, time, traceback
import itertools, logging, logging.config, weakref
import common
import MySQLdb
from autotest_lib.frontend import setup_django_environment
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import host_protections, utils
from autotest_lib.database import database_connection
from autotest_lib.frontend.afe import models, rpc_utils
from autotest_lib.scheduler import drone_manager, drones, email_manager
from autotest_lib.scheduler import monitor_db_cleanup
from autotest_lib.scheduler import status_server, scheduler_config


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

# how long to wait for autoserv to write a pidfile
PIDFILE_TIMEOUT = 5 * 60 # 5 min

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

# load the logging settings
scheduler_dir = os.path.join(AUTOTEST_PATH, 'scheduler')
if not os.environ.has_key('AUTOTEST_SCHEDULER_LOG_DIR'):
    os.environ['AUTOTEST_SCHEDULER_LOG_DIR'] = os.path.join(AUTOTEST_PATH, 'logs')
# Here we export the log name, using the same convention as autoserv's results
# directory.
if os.environ.has_key('AUTOTEST_SCHEDULER_LOG_NAME'):
    scheduler_log_name = os.environ['AUTOTEST_SCHEDULER_LOG_NAME']
else:
    scheduler_log_name = 'scheduler.log.%s' % time.strftime('%Y-%m-%d-%H.%M.%S')
    os.environ['AUTOTEST_SCHEDULER_LOG_NAME'] = scheduler_log_name

logging.config.fileConfig(os.path.join(scheduler_dir, 'debug_scheduler.ini'))


def _site_init_monitor_db_dummy():
    return {}


def main():
    try:
        main_without_exception_handling()
    except:
        logging.exception('Exception escaping in monitor_db')
        raise


def main_without_exception_handling():
    usage = 'usage: %prog [options] results_dir'

    parser = optparse.OptionParser(usage)
    parser.add_option('--recover-hosts', help='Try to recover dead hosts',
                      action='store_true')
    parser.add_option('--logfile', help='Set a log file that all stdout ' +
                      'should be redirected to.  Stderr will go to this ' +
                      'file + ".err"')
    parser.add_option('--test', help='Indicate that scheduler is under ' +
                      'test and should use dummy autoserv and no parsing',
                      action='store_true')
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.print_usage()
        return

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
        init(options.logfile)
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


def handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    logging.info("Shutdown request received.")


def init(logfile):
    if logfile:
        enable_logging(logfile)
    logging.info("%s> dispatcher starting", time.strftime("%X %x"))
    logging.info("My PID is %d", os.getpid())

    utils.write_pid("monitor_db")

    if _testing_mode:
        global_config.global_config.override_config_value(
            DB_CONFIG_SECTION, 'database', 'stresstest_autotest_web')

    os.environ['PATH'] = AUTOTEST_SERVER_DIR + ':' + os.environ['PATH']
    global _db
    _db = database_connection.DatabaseConnection(DB_CONFIG_SECTION)
    _db.connect()

    # ensure Django connection is in autocommit
    setup_django_environment.enable_autocommit()

    logging.info("Setting signal handler")
    signal.signal(signal.SIGINT, handle_sigint)

    drones = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'drones', default='localhost')
    drone_list = [hostname.strip() for hostname in drones.split(',')]
    results_host = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'results_host', default='localhost')
    _drone_manager.initialize(RESULTS_DIR, drone_list, results_host)

    logging.info("Connected! Running...")


def enable_logging(logfile):
    out_file = logfile
    err_file = "%s.err" % logfile
    logging.info("Enabling logging to %s (%s)", out_file, err_file)
    out_fd = open(out_file, "a", buffering=0)
    err_fd = open(err_file, "a", buffering=0)

    os.dup2(out_fd.fileno(), sys.stdout.fileno())
    os.dup2(err_fd.fileno(), sys.stderr.fileno())

    sys.stdout = out_fd
    sys.stderr = err_fd


def _autoserv_command_line(machines, results_dir, extra_args, job=None,
                           queue_entry=None):
    """
    @returns The autoserv command line as a list of executable + parameters.

    @param machines - string - A machine or comma separated list of machines
            for the (-m) flag.
    @param results_dir - string - Where the results will be written (-r).
    @param extra_args - list - Additional arguments to pass to autoserv.
    @param job - Job object - If supplied, -u owner and -l name parameters
            will be added.
    @param queue_entry - A HostQueueEntry object - If supplied and no Job
            object was supplied, this will be used to lookup the Job object.
    """
    autoserv_argv = [_autoserv_path, '-p', '-m', machines,
                     '-r', _drone_manager.absolute_path(results_dir)]
    if job or queue_entry:
        if not job:
            job = queue_entry.job
        autoserv_argv += ['-u', job.owner, '-l', job.name]
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

        @param host_labels - A list of label ids that the host has.
        @param queue_entry - The HostQueueEntry being considered for the host.

        @returns True if atomic group settings are okay, False otherwise.
        """
        return (self._get_host_atomic_group_id(host_labels) ==
                queue_entry.atomic_group_id)


    def _get_host_atomic_group_id(self, host_labels):
        """
        Return the atomic group label id for a host with the given set of
        labels if any, or None otherwise.  Raises an exception if more than
        one atomic group are found in the set of labels.

        @param host_labels - A list of label ids that the host has.

        @returns The id of the atomic group found on a label in host_labels
                or None if no atomic group label is found.
        @raises SchedulerError - If more than one atomic group label is found.
        """
        atomic_ids = [self._labels[label_id].atomic_group_id
                      for label_id in host_labels
                      if self._labels[label_id].atomic_group_id is not None]
        if not atomic_ids:
            return None
        if len(atomic_ids) > 1:
            raise SchedulerError('More than one atomic label on host.')
        return atomic_ids[0]


    def _get_atomic_group_labels(self, atomic_group_id):
        """
        Lookup the label ids that an atomic_group is associated with.

        @param atomic_group_id - The id of the AtomicGroup to look up.

        @returns A generator yeilding Label ids for this atomic group.
        """
        return (id for id, label in self._labels.iteritems()
                if label.atomic_group_id == atomic_group_id
                and not label.invalid)


    def _get_eligible_hosts_in_group(self, group_hosts, queue_entry):
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
        job_dependencies = self._job_dependencies.get(queue_entry.job_id, set())
        host_labels = self._host_labels.get(host_id, set())

        return (self._is_acl_accessible(host_id, queue_entry) and
                self._check_job_dependencies(job_dependencies, host_labels) and
                self._check_only_if_needed_labels(
                    job_dependencies, host_labels, queue_entry) and
                self._check_atomic_group_labels(host_labels, queue_entry))


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
        atomic_group = AtomicGroup(id=queue_entry.atomic_group_id)
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
            eligible_hosts_in_group = self._get_eligible_hosts_in_group(
                    group_hosts, queue_entry)

            # Job.synch_count is treated as "minimum synch count" when
            # scheduling for an atomic group of hosts.  The atomic group
            # number of machines is the maximum to pick out of a single
            # atomic group label for scheduling at one time.
            min_hosts = job.synch_count
            max_hosts = atomic_group.max_number_of_machines

            if len(eligible_hosts_in_group) < min_hosts:
                # Not enough eligible hosts in this atomic group label.
                continue

            # So that they show up in a sane order when viewing the job.
            eligible_hosts_in_group = sorted(eligible_hosts_in_group)

            # Limit ourselves to scheduling the atomic group size.
            if len(eligible_hosts_in_group) > max_hosts:
                eligible_hosts_in_group = eligible_hosts_in_group[:max_hosts]

            # Remove the selected hosts from our cached internal state
            # of available hosts in order to return the Host objects.
            host_list = []
            for host_id in eligible_hosts_in_group:
                hosts_in_label.discard(host_id)
                host_list.append(self._hosts_available.pop(host_id))
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
        self._find_reverify()
        self._process_recurring_runs()
        self._schedule_new_jobs()
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


    def _recover_processes(self):
        self._register_pidfiles()
        _drone_manager.refresh()
        self._recover_all_recoverable_entries()
        self._requeue_other_active_entries()
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
        for queue_entry in queue_entries:
            for pidfile_name in _ALL_PIDFILE_NAMES:
                pidfile_id = _drone_manager.get_pidfile_id_from(
                    queue_entry.execution_tag(), pidfile_name=pidfile_name)
                _drone_manager.register_pidfile(pidfile_id)


    def _recover_entries_with_status(self, status, orphans, pidfile_name,
                                     recover_entries_fn):
        queue_entries = HostQueueEntry.fetch(where="status = '%s'" % status)
        for queue_entry in queue_entries:
            if self.get_agents_for_entry(queue_entry):
                # synchronous job we've already recovered
                continue
            queue_entries = queue_entry.job.get_group_entries(queue_entry)
            execution_tag = queue_entry.execution_tag()
            run_monitor = PidfileRunMonitor()
            run_monitor.attach_to_existing_process(execution_tag,
                                                   pidfile_name=pidfile_name)

            log_message = ('Recovering %s entry %s ' %
                           (status.lower(),
                            ', '.join(str(entry) for entry in queue_entries)))
            if not run_monitor.has_process():
                # execution apparently never happened
                logging.info(log_message + 'without process')
                recover_entries_fn(queue_entry.job, queue_entries, None)
                continue

            logging.info(log_message + '(process %s)',
                         run_monitor.get_process())
            recover_entries_fn(queue_entry.job, queue_entries, run_monitor)
            orphans.discard(run_monitor.get_process())


    def _kill_remaining_orphan_processes(self, orphans):
        for process in orphans:
            logging.info('Killing orphan %s', process)
            _drone_manager.kill_process(process)


    def _recover_running_entries(self, orphans):
        def recover_entries(job, queue_entries, run_monitor):
            if run_monitor is not None:
                queue_task = RecoveryQueueTask(job=job,
                                               queue_entries=queue_entries,
                                               run_monitor=run_monitor)
                self.add_agent(Agent(tasks=[queue_task],
                                     num_processes=len(queue_entries)))
            # else, _requeue_other_active_entries will cover this

        self._recover_entries_with_status(models.HostQueueEntry.Status.RUNNING,
                                          orphans, '.autoserv_execute',
                                          recover_entries)


    def _recover_gathering_entries(self, orphans):
        def recover_entries(job, queue_entries, run_monitor):
            gather_task = GatherLogsTask(job, queue_entries,
                                         run_monitor=run_monitor)
            self.add_agent(Agent([gather_task]))

        self._recover_entries_with_status(
            models.HostQueueEntry.Status.GATHERING,
            orphans, _CRASHINFO_PID_FILE, recover_entries)


    def _recover_parsing_entries(self, orphans):
        def recover_entries(job, queue_entries, run_monitor):
            reparse_task = FinalReparseTask(queue_entries,
                                            run_monitor=run_monitor)
            self.add_agent(Agent([reparse_task], num_processes=0))

        self._recover_entries_with_status(models.HostQueueEntry.Status.PARSING,
                                          orphans, _PARSER_PID_FILE,
                                          recover_entries)


    def _recover_all_recoverable_entries(self):
        orphans = _drone_manager.get_orphaned_autoserv_processes()
        self._recover_running_entries(orphans)
        self._recover_gathering_entries(orphans)
        self._recover_parsing_entries(orphans)
        self._kill_remaining_orphan_processes(orphans)


    def _requeue_other_active_entries(self):
        queue_entries = HostQueueEntry.fetch(
            where='active AND NOT complete AND '
                  '(aborted OR status != "Pending")')
        for queue_entry in queue_entries:
            if self.get_agents_for_entry(queue_entry):
                # entry has already been recovered
                continue
            if queue_entry.aborted:
                queue_entry.abort(self)
                continue

            logging.info('Requeuing active QE %s (status=%s)', queue_entry,
                         queue_entry.status)
            if queue_entry.host:
                tasks = queue_entry.host.reverify_tasks()
                self.add_agent(Agent(tasks))
            agent = queue_entry.requeue()


    def _find_reverify(self):
        self._reverify_hosts_where("status = 'Reverify'")


    def _reverify_remaining_hosts(self):
        # reverify hosts that were in the middle of verify, repair or cleanup
        self._reverify_hosts_where("""(status = 'Repairing' OR
                                       status = 'Verifying' OR
                                       status = 'Cleaning')""")

        # recover "Running" hosts with no active queue entries, although this
        # should never happen
        message = ('Recovering running host %s - this probably indicates a '
                   'scheduler bug')
        self._reverify_hosts_where("""status = 'Running' AND
                                      id NOT IN (SELECT host_id
                                                 FROM host_queue_entries
                                                 WHERE active)""",
                                   print_message=message)


    def _reverify_hosts_where(self, where,
                              print_message='Reverifying host %s'):
        full_where='locked = 0 AND invalid = 0 AND ' + where
        for host in Host.fetch(where=full_where):
            if self.host_has_agent(host):
                # host has already been recovered in some way
                continue
            if print_message:
                logging.info(print_message, host.hostname)
            tasks = host.reverify_tasks()
            self.add_agent(Agent(tasks))


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


    def _run_queue_entry(self, queue_entry, host):
        agent = queue_entry.run(assigned_host=host)
        # in some cases (synchronous jobs with run_verify=False), agent may be
        # None
        if agent:
            self.add_agent(agent)


    def _find_aborting(self):
        for entry in HostQueueEntry.fetch(where='aborted and not complete'):
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
            if agent.is_done():
                logging.info("agent finished")
                self.remove_agent(agent)
                continue
            if not agent.is_running():
                if not self._can_start_agent(agent, num_started_this_cycle,
                                             have_reached_limit):
                    have_reached_limit = True
                    continue
                num_started_this_cycle += agent.num_processes
            agent.tick()
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


    def attach_to_existing_process(self, execution_tag,
                                   pidfile_name=_AUTOSERV_PID_FILE):
        self._set_start_time()
        self.pidfile_id = _drone_manager.get_pidfile_id_from(
            execution_tag, pidfile_name=pidfile_name)
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
        logging.info(message)
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
        logging.info(message)
        if time.time() - self._start_time > PIDFILE_TIMEOUT:
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
        self._get_pidfile_info()
        assert self._state.num_tests_failed is not None
        return self._state.num_tests_failed


class Agent(object):
    def __init__(self, tasks, num_processes=1):
        self.active_task = None
        self.queue = None
        self.dispatcher = None
        self.num_processes = num_processes

        self.queue_entry_ids = self._union_ids(task.queue_entry_ids
                                               for task in tasks)
        self.host_ids = self._union_ids(task.host_ids for task in tasks)

        self._clear_queue()
        for task in tasks:
            self.add_task(task)


    def _clear_queue(self):
        self.queue = Queue.Queue(0)


    def _union_ids(self, id_lists):
        return set(itertools.chain(*id_lists))


    def add_task(self, task):
        self.queue.put_nowait(task)
        task.agent = self


    def tick(self):
        while not self.is_done():
            if self.active_task:
                self.active_task.poll()
                if not self.active_task.is_done():
                    return
            self._next_task()


    def _next_task(self):
        logging.info("agent picking task")
        if self.active_task is not None:
            assert self.active_task.is_done()
            if not self.active_task.success:
                self.on_task_failure()
            self.active_task = None

        if not self.is_done():
            self.active_task = self.queue.get_nowait()


    def on_task_failure(self):
        self._clear_queue()
        # run failure tasks in a new Agent, so host_ids and queue_entry_ids will
        # get reset.
        new_agent = Agent(self.active_task.failure_tasks)
        self.dispatcher.add_agent(new_agent)


    def is_running(self):
        return self.active_task is not None


    def is_done(self):
        return self.active_task is None and self.queue.empty()


    def abort(self):
        # abort tasks until the queue is empty or a task ignores the abort
        while not self.is_done():
            if not self.active_task:
                self._next_task()
            self.active_task.abort()
            if not self.active_task.aborted:
                # tasks can choose to ignore aborts
                return
            self.active_task = None


class AgentTask(object):
    def __init__(self, cmd, working_directory=None, failure_tasks=[],
                 pidfile_name=None, paired_with_pidfile=None):
        self.done = False
        self.failure_tasks = failure_tasks
        self.started = False
        self.cmd = cmd
        self._working_directory = working_directory
        self.task = None
        self.agent = None
        self.monitor = None
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
        pass


    def create_temp_resultsdir(self, suffix=''):
        self.temp_results_dir = _drone_manager.get_temporary_path('agent_task')


    def cleanup(self):
        if self.monitor and self.monitor.has_process() and self.log_file:
            _drone_manager.copy_to_results_repository(
                self.monitor.get_process(), self.log_file)


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


    def set_host_log_file(self, base_name, host):
        filename = '%s.%s' % (time.time(), base_name)
        self.log_file = os.path.join('hosts', host.hostname, filename)


    def _get_consistent_execution_tag(self, queue_entries):
        first_execution_tag = queue_entries[0].execution_tag()
        for queue_entry in queue_entries[1:]:
            assert queue_entry.execution_tag() == first_execution_tag, (
                '%s (%s) != %s (%s)' % (queue_entry.execution_tag(),
                                        queue_entry,
                                        first_execution_tag,
                                        queue_entries[0]))
        return first_execution_tag


    def _copy_results(self, queue_entries, use_monitor=None):
        assert len(queue_entries) > 0
        if use_monitor is None:
            assert self.monitor
            use_monitor = self.monitor
        assert use_monitor.has_process()
        execution_tag = self._get_consistent_execution_tag(queue_entries)
        results_path = execution_tag + '/'
        _drone_manager.copy_to_results_repository(use_monitor.get_process(),
                                                  results_path)


    def _parse_results(self, queue_entries):
        reparse_task = FinalReparseTask(queue_entries)
        self.agent.dispatcher.add_agent(Agent([reparse_task], num_processes=0))


    def _copy_and_parse_results(self, queue_entries, use_monitor=None):
        self._copy_results(queue_entries, use_monitor)
        self._parse_results(queue_entries)


    def run(self, pidfile_name=_AUTOSERV_PID_FILE, paired_with_pidfile=None):
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


class RepairTask(AgentTask, TaskWithJobKeyvals):
    def __init__(self, host, queue_entry=None):
        """\
        queue_entry: queue entry to mark failed if this repair fails.
        """
        protection = host_protections.Protection.get_string(host.protection)
        # normalize the protection name
        protection = host_protections.Protection.get_attr_name(protection)

        self.host = host
        self.queue_entry_to_fail = queue_entry
        # *don't* include the queue entry in IDs -- if the queue entry is
        # aborted, we want to leave the repair task running
        self._set_ids(host=host)

        self.create_temp_resultsdir('.repair')
        cmd = _autoserv_command_line(host.hostname, self.temp_results_dir,
                                     ['-R', '--host-protection', protection],
                                     queue_entry=queue_entry)
        super(RepairTask, self).__init__(cmd, self.temp_results_dir)

        self.set_host_log_file('repair', self.host)


    def prolog(self):
        logging.info("repair_task starting")
        self.host.set_status('Repairing')
        if self.queue_entry_to_fail:
            self.queue_entry_to_fail.requeue()


    def _keyval_path(self):
        return os.path.join(self.temp_results_dir, self._KEYVAL_FILE)


    def _fail_queue_entry(self):
        assert self.queue_entry_to_fail

        if self.queue_entry_to_fail.meta_host:
            return # don't fail metahost entries, they'll be reassigned

        self.queue_entry_to_fail.update_from_database()
        if self.queue_entry_to_fail.status != 'Queued':
            return # entry has been aborted

        self.queue_entry_to_fail.set_execution_subdir()
        queued_key, queued_time = self._job_queued_keyval(
            self.queue_entry_to_fail.job)
        self._write_keyval_after_job(queued_key, queued_time)
        self._write_job_finished()
        # copy results logs into the normal place for job results
        _drone_manager.copy_results_on_drone(
            self.monitor.get_process(),
            source_path=self.temp_results_dir + '/',
            destination_path=self.queue_entry_to_fail.execution_tag() + '/')

        self._copy_results([self.queue_entry_to_fail])
        if self.queue_entry_to_fail.job.parse_failed_repair:
            self._parse_results([self.queue_entry_to_fail])
        self.queue_entry_to_fail.handle_host_failure()


    def epilog(self):
        super(RepairTask, self).epilog()
        if self.success:
            self.host.set_status('Ready')
        else:
            self.host.set_status('Repair Failed')
            if self.queue_entry_to_fail:
                self._fail_queue_entry()


class PreJobTask(AgentTask):
    def epilog(self):
        super(PreJobTask, self).epilog()
        should_copy_results = (self.queue_entry and not self.success
                               and not self.queue_entry.meta_host)
        if should_copy_results:
            self.queue_entry.set_execution_subdir()
            destination = os.path.join(self.queue_entry.execution_tag(),
                                       os.path.basename(self.log_file))
            _drone_manager.copy_to_results_repository(
                self.monitor.get_process(), self.log_file,
                destination_path=destination)


class VerifyTask(PreJobTask):
    def __init__(self, queue_entry=None, host=None):
        assert bool(queue_entry) != bool(host)
        self.host = host or queue_entry.host
        self.queue_entry = queue_entry

        self.create_temp_resultsdir('.verify')
        cmd = _autoserv_command_line(self.host.hostname, self.temp_results_dir,
                                     ['-v'], queue_entry=queue_entry)
        failure_tasks = [RepairTask(self.host, queue_entry=queue_entry)]
        super(VerifyTask, self).__init__(cmd, self.temp_results_dir,
                                         failure_tasks=failure_tasks)

        self.set_host_log_file('verify', self.host)
        self._set_ids(host=host, queue_entries=[queue_entry])


    def prolog(self):
        super(VerifyTask, self).prolog()
        logging.info("starting verify on %s", self.host.hostname)
        if self.queue_entry:
            self.queue_entry.set_status('Verifying')
        self.host.set_status('Verifying')


    def epilog(self):
        super(VerifyTask, self).epilog()

        if self.success:
            self.host.set_status('Ready')


class QueueTask(AgentTask, TaskWithJobKeyvals):
    def __init__(self, job, queue_entries, cmd, group_name=''):
        self.job = job
        self.queue_entries = queue_entries
        self.group_name = group_name
        super(QueueTask, self).__init__(cmd, self._execution_tag())
        self._set_ids(queue_entries=queue_entries)


    def _keyval_path(self):
        return os.path.join(self._execution_tag(), self._KEYVAL_FILE)


    def _write_keyvals_before_job_helper(self, keyval_dict, keyval_path):
        keyval_contents = '\n'.join(self._format_keyval(key, value)
                                    for key, value in keyval_dict.iteritems())
        # always end with a newline to allow additional keyvals to be written
        keyval_contents += '\n'
        _drone_manager.attach_file_to_execution(self._execution_tag(),
                                                keyval_contents,
                                                file_path=keyval_path)


    def _write_keyvals_before_job(self, keyval_dict):
        self._write_keyvals_before_job_helper(keyval_dict, self._keyval_path())


    def _write_host_keyvals(self, host):
        keyval_path = os.path.join(self._execution_tag(), 'host_keyvals',
                                   host.hostname)
        platform, all_labels = host.platform_and_labels()
        keyval_dict = dict(platform=platform, labels=','.join(all_labels))
        self._write_keyvals_before_job_helper(keyval_dict, keyval_path)


    def _execution_tag(self):
        return self.queue_entries[0].execution_tag()


    def prolog(self):
        queued_key, queued_time = self._job_queued_keyval(self.job)
        keyval_dict = {queued_key: queued_time}
        if self.group_name:
            keyval_dict['host_group_name'] = self.group_name
        self._write_keyvals_before_job(keyval_dict)
        for queue_entry in self.queue_entries:
            self._write_host_keyvals(queue_entry.host)
            queue_entry.set_status('Running')
            queue_entry.update_field('started_on', datetime.datetime.now())
            queue_entry.host.set_status('Running')
            queue_entry.host.update_field('dirty', 1)
        if self.job.synch_count == 1:
            assert len(self.queue_entries) == 1
            self.job.write_to_machines_file(self.queue_entries[0])


    def _write_lost_process_error_file(self):
        error_file_path = os.path.join(self._execution_tag(), 'job_failure')
        _drone_manager.write_lines_to_file(error_file_path,
                                           [_LOST_PROCESS_ERROR])


    def _finish_task(self):
        if not self.monitor:
            return

        self._write_job_finished()

        # both of these conditionals can be true, iff the process ran, wrote a
        # pid to its pidfile, and then exited without writing an exit code
        if self.monitor.has_process():
            gather_task = GatherLogsTask(self.job, self.queue_entries)
            self.agent.dispatcher.add_agent(Agent(tasks=[gather_task]))

        if self.monitor.lost_process:
            self._write_lost_process_error_file()
            for queue_entry in self.queue_entries:
                queue_entry.set_status(models.HostQueueEntry.Status.FAILED)


    def _write_status_comment(self, comment):
        _drone_manager.write_lines_to_file(
            os.path.join(self._execution_tag(), 'status.log'),
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


class RecoveryQueueTask(QueueTask):
    def __init__(self, job, queue_entries, run_monitor):
        super(RecoveryQueueTask, self).__init__(job, queue_entries, cmd=None)
        self.run_monitor = run_monitor


    def run(self):
        self.monitor = self.run_monitor


    def prolog(self):
        # recovering an existing process - don't do prolog
        pass


class PostJobTask(AgentTask):
    def __init__(self, queue_entries, pidfile_name, logfile_name,
                 run_monitor=None):
        """
        If run_monitor != None, we're recovering a running task.
        """
        self._queue_entries = queue_entries
        self._pidfile_name = pidfile_name
        self._run_monitor = run_monitor

        self._execution_tag = self._get_consistent_execution_tag(queue_entries)
        self._results_dir = _drone_manager.absolute_path(self._execution_tag)
        self._autoserv_monitor = PidfileRunMonitor()
        self._autoserv_monitor.attach_to_existing_process(self._execution_tag)
        self._paired_with_pidfile = self._autoserv_monitor.pidfile_id

        if _testing_mode:
            command = 'true'
        else:
            command = self._generate_command(self._results_dir)

        super(PostJobTask, self).__init__(cmd=command,
                                          working_directory=self._execution_tag)

        self.log_file = os.path.join(self._execution_tag, logfile_name)
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
        if self._run_monitor is not None:
            self.monitor = self._run_monitor
        else:
            # make sure we actually have results to work with.
            # this should never happen in normal operation.
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


class GatherLogsTask(PostJobTask):
    """
    Task responsible for
    * gathering uncollected logs (if Autoserv crashed hard or was killed)
    * copying logs to the results repository
    * spawning CleanupTasks for hosts, if necessary
    * spawning a FinalReparseTask for the job
    """
    def __init__(self, job, queue_entries, run_monitor=None):
        self._job = job
        super(GatherLogsTask, self).__init__(
            queue_entries, pidfile_name=_CRASHINFO_PID_FILE,
            logfile_name='.collect_crashinfo.log', run_monitor=run_monitor)
        self._set_ids(queue_entries=queue_entries)


    def _generate_command(self, results_dir):
        host_list = ','.join(queue_entry.host.hostname
                             for queue_entry in self._queue_entries)
        return [_autoserv_path , '-p', '--collect-crashinfo', '-m', host_list,
                '-r', results_dir]


    def prolog(self):
        super(GatherLogsTask, self).prolog()
        self._set_all_statuses(models.HostQueueEntry.Status.GATHERING)


    def _reboot_hosts(self):
        reboot_after = self._job.reboot_after
        do_reboot = False
        if self._final_status == models.HostQueueEntry.Status.ABORTED:
            do_reboot = True
        elif reboot_after == models.RebootAfter.ALWAYS:
            do_reboot = True
        elif reboot_after == models.RebootAfter.IF_ALL_TESTS_PASSED:
            final_success = (
                self._final_status == models.HostQueueEntry.Status.COMPLETED)
            num_tests_failed = self._autoserv_monitor.num_tests_failed()
            do_reboot = (final_success and num_tests_failed == 0)

        for queue_entry in self._queue_entries:
            if do_reboot:
                # don't pass the queue entry to the CleanupTask. if the cleanup
                # fails, the job doesn't care -- it's over.
                cleanup_task = CleanupTask(host=queue_entry.host)
                self.agent.dispatcher.add_agent(Agent([cleanup_task]))
            else:
                queue_entry.host.set_status('Ready')


    def epilog(self):
        super(GatherLogsTask, self).epilog()
        if self._autoserv_monitor.has_process():
            self._copy_and_parse_results(self._queue_entries,
                                         use_monitor=self._autoserv_monitor)
        self._reboot_hosts()


    def run(self):
        autoserv_exit_code = self._autoserv_monitor.exit_code()
        # only run if Autoserv exited due to some signal. if we have no exit
        # code, assume something bad (and signal-like) happened.
        if autoserv_exit_code is None or os.WIFSIGNALED(autoserv_exit_code):
            super(GatherLogsTask, self).run()
        else:
            self.finished(True)


class CleanupTask(PreJobTask):
    def __init__(self, host=None, queue_entry=None):
        assert bool(host) ^ bool(queue_entry)
        if queue_entry:
            host = queue_entry.get_host()
        self.queue_entry = queue_entry
        self.host = host

        self.create_temp_resultsdir('.cleanup')
        self.cmd = _autoserv_command_line(host.hostname, self.temp_results_dir,
                                          ['--cleanup'],
                                          queue_entry=queue_entry)
        repair_task = RepairTask(host, queue_entry=queue_entry)
        super(CleanupTask, self).__init__(self.cmd, self.temp_results_dir,
                                          failure_tasks=[repair_task])

        self._set_ids(host=host, queue_entries=[queue_entry])
        self.set_host_log_file('cleanup', self.host)


    def prolog(self):
        super(CleanupTask, self).prolog()
        logging.info("starting cleanup task for host: %s", self.host.hostname)
        self.host.set_status("Cleaning")


    def epilog(self):
        super(CleanupTask, self).epilog()
        if self.success:
            self.host.set_status('Ready')
            self.host.update_field('dirty', 0)


class FinalReparseTask(PostJobTask):
    _num_running_parses = 0

    def __init__(self, queue_entries, run_monitor=None):
        super(FinalReparseTask, self).__init__(queue_entries,
                                               pidfile_name=_PARSER_PID_FILE,
                                               logfile_name='.parse.log',
                                               run_monitor=run_monitor)
        # don't use _set_ids, since we don't want to set the host_ids
        self.queue_entry_ids = [entry.id for entry in queue_entries]
        self._parse_started = False


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
        super(FinalReparseTask, self).prolog()
        self._set_all_statuses(models.HostQueueEntry.Status.PARSING)


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


class SetEntryPendingTask(AgentTask):
    def __init__(self, queue_entry):
        super(SetEntryPendingTask, self).__init__(cmd='')
        self._queue_entry = queue_entry
        self._set_ids(queue_entries=[queue_entry])


    def run(self):
        agent = self._queue_entry.on_pending()
        if agent:
            self.agent.dispatcher.add_agent(agent)
        self.finished(True)


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
        assert (bool(id) != bool(row))
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
        for row in rows:
            yield cls(row=row)


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


class Host(DBObject):
    _table_name = 'hosts'
    _fields = ('id', 'hostname', 'locked', 'synch_id', 'status',
               'invalid', 'protection', 'locked_by_id', 'lock_time', 'dirty')


    def current_task(self):
        rows = _db.execute("""
                SELECT * FROM host_queue_entries WHERE host_id=%s AND NOT complete AND active
                """, (self.id,))

        if len(rows) == 0:
            return None
        else:
            assert len(rows) == 1
            results = rows[0];
            return HostQueueEntry(row=results)


    def yield_work(self):
        logging.info("%s yielding work", self.hostname)
        if self.current_task():
            self.current_task().requeue()


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


    def reverify_tasks(self):
        cleanup_task = CleanupTask(host=self)
        verify_task = VerifyTask(host=self)
        # just to make sure this host does not get taken away
        self.set_status('Cleaning')
        return [cleanup_task, verify_task]


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
        return "%s/%d (%d)" % (self._get_hostname(), self.job.id, self.id)


    def set_status(self, status):
        self.update_field('status', status)

        logging.info("%s -> %s", self, self.status)

        if status in ['Queued', 'Parsing']:
            self.update_field('complete', False)
            self.update_field('active', False)

        if status in ['Pending', 'Running', 'Verifying', 'Starting',
                      'Gathering']:
            self.update_field('complete', False)
            self.update_field('active', True)

        if status in ['Failed', 'Completed', 'Stopped', 'Aborted']:
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


    def run(self, assigned_host=None):
        if self.meta_host is not None or self.atomic_group_id is not None:
            assert assigned_host
            # ensure results dir exists for the queue log
            self.set_host(assigned_host)

        logging.info("%s/%s/%s scheduled on %s, status=%s", 
                     self.job.name, self.meta_host, self.atomic_group_id,
                     self.host.hostname, self.status)

        return self.job.run(queue_entry=self)


    def requeue(self):
        self.set_status('Queued')
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
        self.set_status('Failed')
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
        job is ready to run, returns an agent to run the job.  Returns None
        otherwise.
        """
        self.set_status('Pending')
        self.get_host().set_status('Pending')
        if self.job.is_ready():
            return self.job.run(self)
        self.job.stop_if_necessary()
        return None


    def abort(self, dispatcher):
        assert self.aborted and not self.complete

        Status = models.HostQueueEntry.Status
        has_running_job_agent = (
            self.status in (Status.RUNNING, Status.GATHERING, Status.PARSING)
            and dispatcher.get_agents_for_entry(self))
        if has_running_job_agent:
            # do nothing; post-job tasks will finish and then mark this entry
            # with status "Aborted" and take care of the host
            return

        if self.status in (Status.STARTING, Status.PENDING):
            self.host.set_status(models.Host.Status.READY)
        elif self.status == Status.VERIFYING:
            dispatcher.add_agent(Agent(tasks=self.host.reverify_tasks()))

        self.set_status(Status.ABORTED)

    def execution_tag(self):
        assert self.execution_subdir
        return "%s-%s/%s" % (self.job.id, self.job.owner, self.execution_subdir)


class Job(DBObject):
    _table_name = 'jobs'
    _fields = ('id', 'owner', 'name', 'priority', 'control_file',
               'control_type', 'created_on', 'synch_count', 'timeout',
               'run_verify', 'email_list', 'reboot_before', 'reboot_after',
               'parse_failed_repair', 'max_runtime_hrs')


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


    def is_ready(self):
        pending_entries = models.HostQueueEntry.objects.filter(job=self.id,
                                                               status='Pending')
        return (pending_entries.count() >= self.synch_count)


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


    def _write_control_file(self, execution_tag):
        control_path = _drone_manager.attach_file_to_execution(
                execution_tag, self.control_file)
        return control_path


    def get_group_entries(self, queue_entry_from_group):
        execution_subdir = queue_entry_from_group.execution_subdir
        return list(HostQueueEntry.fetch(
            where='job_id=%s AND execution_subdir=%s',
            params=(self.id, execution_subdir)))


    def _get_autoserv_params(self, queue_entries):
        assert queue_entries
        execution_tag = queue_entries[0].execution_tag()
        control_path = self._write_control_file(execution_tag)
        hostnames = ','.join([entry.get_host().hostname
                              for entry in queue_entries])

        params = _autoserv_command_line(
            hostnames, execution_tag,
            ['-P', execution_tag, '-n',
             _drone_manager.absolute_path(control_path)],
            job=self)

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


    def _get_pre_job_tasks(self, queue_entry):
        tasks = []
        if self._should_run_cleanup(queue_entry):
            tasks.append(CleanupTask(queue_entry=queue_entry))
        if self._should_run_verify(queue_entry):
            tasks.append(VerifyTask(queue_entry=queue_entry))
        tasks.append(SetEntryPendingTask(queue_entry))
        return tasks


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
                to this job a results database.
        """
        if include_queue_entry.atomic_group_id:
            atomic_group = AtomicGroup(include_queue_entry.atomic_group_id,
                                       always_query=False)
        else:
            atomic_group = None

        chosen_entries = [include_queue_entry]
        if atomic_group:
            num_entries_wanted = atomic_group.max_number_of_machines
        else:
            num_entries_wanted = self.synch_count
        num_entries_wanted -= len(chosen_entries)

        if num_entries_wanted > 0:
            where_clause = 'job_id = %s AND status = "Pending" AND id != %s'
            pending_entries = HostQueueEntry.fetch(
                     where=where_clause,
                     params=(self.id, include_queue_entry.id))
            # TODO(gps): sort these by hostname before slicing.
            chosen_entries += list(pending_entries)[:num_entries_wanted]

        # Sanity check.  We'll only ever be called if this can be met.
        assert len(chosen_entries) >= self.synch_count

        if atomic_group:
            # Look at any meta_host and dependency labels and pick the first
            # one that also specifies this atomic group.  Use that label name
            # as the group name if possible (it is more specific).
            group_name = atomic_group.name
            for label in include_queue_entry.get_labels():
                if label.atomic_group_id:
                    assert label.atomic_group_id == atomic_group.id
                    group_name = label.name
                    break
        else:
            group_name = ''

        self._assign_new_group(chosen_entries, group_name=group_name)
        return chosen_entries, group_name


    def run(self, queue_entry):
        if not self.is_ready():
            queue_entry.set_status(models.HostQueueEntry.Status.VERIFYING)
            return Agent(self._get_pre_job_tasks(queue_entry))

        queue_entries, group_name = self._choose_group_to_run(queue_entry)
        return self._finish_run(queue_entries, group_name)


    def _finish_run(self, queue_entries, group_name):
        for queue_entry in queue_entries:
            queue_entry.set_status('Starting')
        params = self._get_autoserv_params(queue_entries)
        queue_task = QueueTask(job=self, queue_entries=queue_entries,
                               cmd=params, group_name=group_name)
        tasks = [queue_task]
        entry_ids = [entry.id for entry in queue_entries]

        return Agent(tasks, num_processes=len(queue_entries))


if __name__ == '__main__':
    main()
