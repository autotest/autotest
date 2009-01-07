#!/usr/bin/python -u

"""
Autotest scheduler
"""


import datetime, errno, MySQLdb, optparse, os, pwd, Queue, re, shutil, signal
import smtplib, socket, stat, subprocess, sys, tempfile, time, traceback
import itertools, logging
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import host_protections, utils, debug
from autotest_lib.database import database_connection
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import drone_manager, drones, email_manager
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

_db = None
_shutdown = False
_autoserv_path = os.path.join(drones.AUTOTEST_INSTALL_DIR, 'server', 'autoserv')
_parser_path = os.path.join(drones.AUTOTEST_INSTALL_DIR, 'tko', 'parse')
_testing_mode = False
_base_url = None
_notify_email_statuses = []
_drone_manager = drone_manager.DroneManager()


def main():
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
            print 'Error: [SERVER] hostname missing from the config file.'
            sys.exit(1)
        _base_url = 'http://%s/afe/' % server_name

    server = status_server.StatusServer()
    server.start()

    init(options.logfile)
    dispatcher = Dispatcher()
    dispatcher.do_initial_recovery(recover_hosts=options.recover_hosts)

    try:
        while not _shutdown:
            dispatcher.tick()
            time.sleep(scheduler_config.config.tick_pause_sec)
    except:
        email_manager.manager.log_stacktrace(
            "Uncaught exception; terminating monitor_db")

    email_manager.manager.send_queued_emails()
    _drone_manager.shutdown()
    _db.disconnect()


def handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print "Shutdown request received."


def init(logfile):
    if logfile:
        enable_logging(logfile)
    print "%s> dispatcher starting" % time.strftime("%X %x")
    print "My PID is %d" % os.getpid()

    if _testing_mode:
        global_config.global_config.override_config_value(
            DB_CONFIG_SECTION, 'database', 'stresstest_autotest_web')

    os.environ['PATH'] = AUTOTEST_SERVER_DIR + ':' + os.environ['PATH']
    global _db
    _db = database_connection.DatabaseConnection(DB_CONFIG_SECTION)
    _db.connect()

    # ensure Django connection is in autocommit
    setup_django_environment.enable_autocommit()

    debug.configure('scheduler', format_string='%(message)s')
    debug.get_logger().setLevel(logging.WARNING)

    print "Setting signal handler"
    signal.signal(signal.SIGINT, handle_sigint)

    drones = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'drones', default='localhost')
    drone_list = [hostname.strip() for hostname in drones.split(',')]
    results_host = global_config.global_config.get_config_value(
        scheduler_config.CONFIG_SECTION, 'results_host', default='localhost')
    _drone_manager.initialize(RESULTS_DIR, drone_list, results_host)

    print "Connected! Running..."


def enable_logging(logfile):
    out_file = logfile
    err_file = "%s.err" % logfile
    print "Enabling logging to %s (%s)" % (out_file, err_file)
    out_fd = open(out_file, "a", buffering=0)
    err_fd = open(err_file, "a", buffering=0)

    os.dup2(out_fd.fileno(), sys.stdout.fileno())
    os.dup2(err_fd.fileno(), sys.stderr.fileno())

    sys.stdout = out_fd
    sys.stderr = err_fd


def queue_entries_to_abort():
    rows = _db.execute("""
            SELECT * FROM host_queue_entries WHERE status='Abort';
                    """)

    qe = [HostQueueEntry(row=i) for i in rows]
    return qe


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
            left_id, right_id = long(row[0]), long(row[1])
            if flip:
                left_id, right_id = right_id, left_id
            result.setdefault(left_id, set()).add(right_id)
        return result


    @classmethod
    def _get_job_acl_groups(cls, job_ids):
        query = """
        SELECT jobs.id, acl_groups_users.acl_group_id
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
        SELECT host_id, acl_group_id
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
        return len(job_dependencies - host_labels) == 0


    def _check_only_if_needed_labels(self, job_dependencies, host_labels,
                                     queue_entry):
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


    def _is_host_eligible_for_job(self, host_id, queue_entry):
        job_dependencies = self._job_dependencies.get(queue_entry.job_id, set())
        host_labels = self._host_labels.get(host_id, set())

        acl = self._is_acl_accessible(host_id, queue_entry)
        deps = self._check_job_dependencies(job_dependencies, host_labels)
        only_if = self._check_only_if_needed_labels(job_dependencies,
                                                    host_labels, queue_entry)
        return acl and deps and only_if


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

            hosts_in_label.remove(host_id)
            return self._hosts_available.pop(host_id)
        return None


    def find_eligible_host(self, queue_entry):
        if not queue_entry.meta_host:
            return self._schedule_non_metahost(queue_entry)
        return self._schedule_metahost(queue_entry)


class Dispatcher(object):
    def __init__(self):
        self._agents = []
        self._last_clean_time = time.time()
        self._host_scheduler = HostScheduler()
        self._host_agents = {}
        self._queue_entry_agents = {}


    def do_initial_recovery(self, recover_hosts=True):
        # always recover processes
        self._recover_processes()

        if recover_hosts:
            self._recover_hosts()


    def tick(self):
        _drone_manager.refresh()
        self._run_cleanup_maybe()
        self._find_aborting()
        self._schedule_new_jobs()
        self._handle_agents()
        _drone_manager.execute_actions()
        email_manager.manager.send_queued_emails()


    def _run_cleanup_maybe(self):
        should_cleanup = (self._last_clean_time +
                          scheduler_config.config.clean_interval * 60 <
                          time.time())
        if should_cleanup:
            print 'Running cleanup'
            self._abort_timed_out_jobs()
            self._abort_jobs_past_synch_start_timeout()
            self._clear_inactive_blocks()
            self._check_for_db_inconsistencies()
            self._last_clean_time = time.time()


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
        return self._queue_entry_agents.get(queue_entry.id, set())


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


    def num_running_processes(self):
        return sum(agent.num_processes for agent in self._agents
                   if agent.is_running())


    def _extract_execution_tag(self, command_line):
        match = re.match(r'.* -P (\S+) ', command_line)
        if not match:
            return None
        return match.group(1)


    def _recover_queue_entries(self, queue_entries, run_monitor):
        assert len(queue_entries) > 0
        queue_task = RecoveryQueueTask(job=queue_entries[0].job,
                                       queue_entries=queue_entries,
                                       run_monitor=run_monitor)
        self.add_agent(Agent(tasks=[queue_task],
                             num_processes=len(queue_entries)))


    def _recover_processes(self):
        self._register_pidfiles()
        _drone_manager.refresh()
        self._recover_running_entries()
        self._recover_aborting_entries()
        self._requeue_other_active_entries()
        self._recover_parsing_entries()
        self._reverify_remaining_hosts()
        # reinitialize drones after killing orphaned processes, since they can
        # leave around files when they die
        _drone_manager.execute_actions()
        _drone_manager.reinitialize_drones()


    def _register_pidfiles(self):
        # during recovery we may need to read pidfiles for both running and
        # parsing entries
        queue_entries = HostQueueEntry.fetch(
            where="status IN ('Running', 'Parsing')")
        for queue_entry in queue_entries:
            pidfile_id = _drone_manager.get_pidfile_id_from(
                queue_entry.execution_tag())
            _drone_manager.register_pidfile(pidfile_id)


    def _recover_running_entries(self):
        orphans = _drone_manager.get_orphaned_autoserv_processes()

        queue_entries = HostQueueEntry.fetch(where="status = 'Running'")
        requeue_entries = []
        for queue_entry in queue_entries:
            if self.get_agents_for_entry(queue_entry):
                # synchronous job we've already recovered
                continue
            execution_tag = queue_entry.execution_tag()
            run_monitor = PidfileRunMonitor()
            run_monitor.attach_to_existing_process(execution_tag)
            if not run_monitor.has_process():
                # autoserv apparently never got run, so let it get requeued
                continue
            queue_entries = queue_entry.job.get_group_entries(queue_entry)
            print 'Recovering %s (process %s)' % (
                ', '.join(str(entry) for entry in queue_entries),
                run_monitor.get_process())
            self._recover_queue_entries(queue_entries, run_monitor)
            orphans.pop(execution_tag, None)

        # now kill any remaining autoserv processes
        for process in orphans.itervalues():
            print 'Killing orphan %s' % process
            _drone_manager.kill_process(process)


    def _recover_aborting_entries(self):
        queue_entries = HostQueueEntry.fetch(
            where='status IN ("Abort", "Aborting")')
        for queue_entry in queue_entries:
            print 'Recovering aborting QE %s' % queue_entry
            agent = queue_entry.abort(self)


    def _requeue_other_active_entries(self):
        queue_entries = HostQueueEntry.fetch(
            where='active AND NOT complete AND status != "Pending"')
        for queue_entry in queue_entries:
            if self.get_agents_for_entry(queue_entry):
                # entry has already been recovered
                continue
            print 'Requeuing active QE %s (status=%s)' % (queue_entry,
                                                          queue_entry.status)
            if queue_entry.host:
                tasks = queue_entry.host.reverify_tasks()
                self.add_agent(Agent(tasks))
            agent = queue_entry.requeue()


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
                print print_message % host.hostname
            tasks = host.reverify_tasks()
            self.add_agent(Agent(tasks))


    def _recover_parsing_entries(self):
        recovered_entry_ids = set()
        for entry in HostQueueEntry.fetch(where='status = "Parsing"'):
            if entry.id in recovered_entry_ids:
                continue
            queue_entries = entry.job.get_group_entries(entry)
            recovered_entry_ids = recovered_entry_ids.union(
                entry.id for entry in queue_entries)
            print 'Recovering parsing entries %s' % (
                ', '.join(str(entry) for entry in queue_entries))

            reparse_task = FinalReparseTask(queue_entries)
            self.add_agent(Agent([reparse_task], num_processes=0))


    def _recover_hosts(self):
        # recover "Repair Failed" hosts
        message = 'Reverifying dead host %s'
        self._reverify_hosts_where("status = 'Repair Failed'",
                                   print_message=message)


    def _abort_timed_out_jobs(self):
        """
        Aborts all jobs that have timed out and not completed
        """
        query = models.Job.objects.filter(hostqueueentry__complete=False).extra(
            where=['created_on + INTERVAL timeout HOUR < NOW()'])
        for job in query.distinct():
            print 'Aborting job %d due to job timeout' % job.id
            job.abort(None)


    def _abort_jobs_past_synch_start_timeout(self):
        """
        Abort synchronous jobs that are past the start timeout (from global
        config) and are holding a machine that's in everyone.
        """
        timeout_delta = datetime.timedelta(
            minutes=scheduler_config.config.synch_job_start_timeout_minutes)
        timeout_start = datetime.datetime.now() - timeout_delta
        query = models.Job.objects.filter(
            created_on__lt=timeout_start,
            hostqueueentry__status='Pending',
            hostqueueentry__host__acl_group__name='Everyone')
        for job in query.distinct():
            print 'Aborting job %d due to start timeout' % job.id
            entries_to_abort = job.hostqueueentry_set.exclude(
                status=models.HostQueueEntry.Status.RUNNING)
            for queue_entry in entries_to_abort:
                queue_entry.abort(None)


    def _clear_inactive_blocks(self):
        """
        Clear out blocks for all completed jobs.
        """
        # this would be simpler using NOT IN (subquery), but MySQL
        # treats all IN subqueries as dependent, so this optimizes much
        # better
        _db.execute("""
            DELETE ihq FROM ineligible_host_queues ihq
            LEFT JOIN (SELECT DISTINCT job_id FROM host_queue_entries
                       WHERE NOT complete) hqe
            USING (job_id) WHERE hqe.job_id IS NULL""")


    def _get_pending_queue_entries(self):
        # prioritize by job priority, then non-metahost over metahost, then FIFO
        return list(HostQueueEntry.fetch(
            where='NOT complete AND NOT active AND status="Queued"',
            order_by='priority DESC, meta_host, job_id'))


    def _schedule_new_jobs(self):
        queue_entries = self._get_pending_queue_entries()
        if not queue_entries:
            return

        self._host_scheduler.refresh(queue_entries)

        for queue_entry in queue_entries:
            assigned_host = self._host_scheduler.find_eligible_host(queue_entry)
            if not assigned_host:
                continue
            self._run_queue_entry(queue_entry, assigned_host)


    def _run_queue_entry(self, queue_entry, host):
        agent = queue_entry.run(assigned_host=host)
        # in some cases (synchronous jobs with run_verify=False), agent may be
        # None
        if agent:
            self.add_agent(agent)


    def _find_aborting(self):
        for entry in queue_entries_to_abort():
            agents_to_abort = list(self.get_agents_for_entry(entry))
            for agent in agents_to_abort:
                self.remove_agent(agent)

            entry.abort(self, agents_to_abort)


    def _can_start_agent(self, agent, num_running_processes,
                         num_started_this_cycle, have_reached_limit):
        # always allow zero-process agents to run
        if agent.num_processes == 0:
            return True
        # don't allow any nonzero-process agents to run after we've reached a
        # limit (this avoids starvation of many-process agents)
        if have_reached_limit:
            return False
        # total process throttling
        if (num_running_processes + agent.num_processes >
            scheduler_config.config.max_running_processes):
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
        num_running_processes = self.num_running_processes()
        num_started_this_cycle = 0
        have_reached_limit = False
        # iterate over copy, so we can remove agents during iteration
        for agent in list(self._agents):
            if agent.is_done():
                print "agent finished"
                self.remove_agent(agent)
                continue
            if not agent.is_running():
                if not self._can_start_agent(agent, num_running_processes,
                                             num_started_this_cycle,
                                             have_reached_limit):
                    have_reached_limit = True
                    continue
                num_running_processes += agent.num_processes
                num_started_this_cycle += agent.num_processes
            agent.tick()
        print num_running_processes, 'running processes'


    def _check_for_db_inconsistencies(self):
        query = models.HostQueueEntry.objects.filter(active=True, complete=True)
        if query.count() != 0:
            subject = ('%d queue entries found with active=complete=1'
                       % query.count())
            message = '\n'.join(str(entry.get_object_dict())
                                for entry in query[:50])
            if len(query) > 50:
                message += '\n(truncated)\n'

            print subject
            email_manager.manager.enqueue_notify_email(subject, message)


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
        self._lost_process = False
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
            command, working_directory, log_file=log_file,
            pidfile_name=pidfile_name, paired_with_pidfile=paired_with_pidfile)


    def attach_to_existing_process(self, execution_tag):
        self._set_start_time()
        self.pidfile_id = _drone_manager.get_pidfile_id_from(execution_tag)
        _drone_manager.register_pidfile(self.pidfile_id)


    def kill(self):
        if self.has_process():
            _drone_manager.kill_process(self.get_process())


    def has_process(self):
        self._get_pidfile_info()
        return self._state.process is not None


    def get_process(self):
        self._get_pidfile_info()
        assert self.has_process()
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
        print message
        email_manager.manager.enqueue_notify_email(error, message)
        if self._state.process is not None:
            process = self._state.process
        else:
            process = _drone_manager.get_dummy_process()
        self.on_lost_process(process)


    def _get_pidfile_info_helper(self):
        if self._lost_process:
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
        print message
        if time.time() - self._start_time > PIDFILE_TIMEOUT:
            email_manager.manager.enqueue_notify_email(
                'Process has failed to write pidfile', message)
            self.on_lost_process(_drone_manager.get_dummy_process())


    def on_lost_process(self, process):
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
        self.queue = Queue.Queue(0)
        self.dispatcher = None
        self.num_processes = num_processes

        self.queue_entry_ids = self._union_ids(task.queue_entry_ids
                                               for task in tasks)
        self.host_ids = self._union_ids(task.host_ids for task in tasks)

        for task in tasks:
            self.add_task(task)


    def _union_ids(self, id_lists):
        return set(itertools.chain(*id_lists))


    def add_task(self, task):
        self.queue.put_nowait(task)
        task.agent = self


    def tick(self):
        while not self.is_done():
            if self.active_task and not self.active_task.is_done():
                self.active_task.poll()
                if not self.active_task.is_done():
                    return
            self._next_task()


    def _next_task(self):
        print "agent picking task"
        if self.active_task:
            assert self.active_task.is_done()

            if not self.active_task.success:
                self.on_task_failure()

        self.active_task = None
        if not self.is_done():
            self.active_task = self.queue.get_nowait()
            if self.active_task:
                self.active_task.start()


    def on_task_failure(self):
        self.queue = Queue.Queue(0)
        for task in self.active_task.failure_tasks:
            self.add_task(task)


    def is_running(self):
        return self.active_task is not None


    def is_done(self):
        return self.active_task is None and self.queue.empty()


    def start(self):
        assert self.dispatcher

        self._next_task()


class AgentTask(object):
    def __init__(self, cmd, working_directory=None, failure_tasks=[]):
        self.done = False
        self.failure_tasks = failure_tasks
        self.started = False
        self.cmd = cmd
        self._working_directory = working_directory
        self.task = None
        self.agent = None
        self.monitor = None
        self.success = None
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
        if self.monitor:
            self.tick(self.monitor.exit_code())
        else:
            self.finished(False)


    def tick(self, exit_code):
        if exit_code is None:
            return
        if exit_code == 0:
            success = True
        else:
            success = False

        self.finished(success)


    def is_done(self):
        return self.done


    def finished(self, success):
        self.done = True
        self.success = success
        self.epilog()


    def prolog(self):
        pass


    def create_temp_resultsdir(self, suffix=''):
        self.temp_results_dir = _drone_manager.get_temporary_path('agent_task')


    def cleanup(self):
        if self.monitor and self.log_file:
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
        self.cleanup()


    def set_host_log_file(self, base_name, host):
        filename = '%s.%s' % (time.time(), base_name)
        self.log_file = os.path.join('hosts', host.hostname, filename)


    def run(self):
        if self.cmd:
            self.monitor = PidfileRunMonitor()
            self.monitor.run(self.cmd, self._working_directory,
                             nice_level=AUTOSERV_NICE_LEVEL,
                             log_file=self.log_file)


class RepairTask(AgentTask):
    def __init__(self, host, queue_entry=None):
        """\
        queue_entry: queue entry to mark failed if this repair fails.
        """
        protection = host_protections.Protection.get_string(host.protection)
        # normalize the protection name
        protection = host_protections.Protection.get_attr_name(protection)

        self.host = host
        self.queue_entry = queue_entry
        self._set_ids(host=host, queue_entries=[queue_entry])

        self.create_temp_resultsdir('.repair')
        cmd = [_autoserv_path , '-p', '-R', '-m', host.hostname,
               '-r', _drone_manager.absolute_path(self.temp_results_dir),
               '--host-protection', protection]
        super(RepairTask, self).__init__(cmd, self.temp_results_dir)

        self._set_ids(host=host, queue_entries=[queue_entry])
        self.set_host_log_file('repair', self.host)


    def prolog(self):
        print "repair_task starting"
        self.host.set_status('Repairing')
        if self.queue_entry:
            self.queue_entry.requeue()


    def epilog(self):
        super(RepairTask, self).epilog()
        if self.success:
            self.host.set_status('Ready')
        else:
            self.host.set_status('Repair Failed')
            if self.queue_entry and not self.queue_entry.meta_host:
                self.queue_entry.handle_host_failure()


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
        cmd = [_autoserv_path, '-p', '-v', '-m', self.host.hostname, '-r',
               _drone_manager.absolute_path(self.temp_results_dir)]
        failure_tasks = [RepairTask(self.host, queue_entry=queue_entry)]
        super(VerifyTask, self).__init__(cmd, self.temp_results_dir,
                                         failure_tasks=failure_tasks)

        self.set_host_log_file('verify', self.host)
        self._set_ids(host=host, queue_entries=[queue_entry])


    def prolog(self):
        super(VerifyTask, self).prolog()
        print "starting verify on %s" % (self.host.hostname)
        if self.queue_entry:
            self.queue_entry.set_status('Verifying')
        self.host.set_status('Verifying')


    def epilog(self):
        super(VerifyTask, self).epilog()

        if self.success:
            self.host.set_status('Ready')
            if self.queue_entry:
                agent = self.queue_entry.on_pending()
                if agent:
                    self.agent.dispatcher.add_agent(agent)


class QueueTask(AgentTask):
    def __init__(self, job, queue_entries, cmd):
        self.job = job
        self.queue_entries = queue_entries
        super(QueueTask, self).__init__(cmd, self._execution_tag())
        self._set_ids(queue_entries=queue_entries)


    def _format_keyval(self, key, value):
        return '%s=%s' % (key, value)


    def _write_keyval(self, field, value):
        keyval_path = os.path.join(self._execution_tag(), 'keyval')
        assert self.monitor and self.monitor.has_process()
        paired_with_pidfile = self.monitor.pidfile_id
        _drone_manager.write_lines_to_file(
            keyval_path, [self._format_keyval(field, value)],
            paired_with_pidfile=paired_with_pidfile)


    def _write_host_keyvals(self, host):
        keyval_path = os.path.join(self._execution_tag(), 'host_keyvals',
                                   host.hostname)
        platform, all_labels = host.platform_and_labels()
        keyvals = dict(platform=platform, labels=','.join(all_labels))
        keyval_content = '\n'.join(self._format_keyval(key, value)
                                   for key, value in keyvals.iteritems())
        _drone_manager.attach_file_to_execution(self._execution_tag(),
                                                keyval_content,
                                                file_path=keyval_path)


    def _execution_tag(self):
        return self.queue_entries[0].execution_tag()


    def prolog(self):
        for queue_entry in self.queue_entries:
            self._write_host_keyvals(queue_entry.host)
            queue_entry.set_status('Running')
            queue_entry.host.set_status('Running')
            queue_entry.host.update_field('dirty', 1)
        if self.job.synch_count == 1:
            assert len(self.queue_entries) == 1
            self.job.write_to_machines_file(self.queue_entries[0])


    def _finish_task(self, success):
        queued = time.mktime(self.job.created_on.timetuple())
        finished = time.time()
        self._write_keyval("job_queued", int(queued))
        self._write_keyval("job_finished", int(finished))

        _drone_manager.copy_to_results_repository(self.monitor.get_process(),
                                                  self._execution_tag() + '/')

        # parse the results of the job
        reparse_task = FinalReparseTask(self.queue_entries)
        self.agent.dispatcher.add_agent(Agent([reparse_task], num_processes=0))


    def _write_status_comment(self, comment):
        _drone_manager.write_lines_to_file(
            os.path.join(self._execution_tag(), 'status.log'),
            ['INFO\t----\t----\t' + comment],
            paired_with_pidfile=self.monitor.pidfile_id)


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

        self._write_keyval("aborted_by", aborted_by_value)
        self._write_keyval("aborted_on", aborted_on_value)

        aborted_on_string = str(datetime.datetime.fromtimestamp(
            aborted_on_value))
        self._write_status_comment('Job aborted by %s on %s' %
                                   (aborted_by_value, aborted_on_string))


    def abort(self):
        super(QueueTask, self).abort()
        self._log_abort()
        self._finish_task(False)


    def _reboot_hosts(self):
        reboot_after = self.job.reboot_after
        do_reboot = False
        if reboot_after == models.RebootAfter.ALWAYS:
            do_reboot = True
        elif reboot_after == models.RebootAfter.IF_ALL_TESTS_PASSED:
            num_tests_failed = self.monitor.num_tests_failed()
            do_reboot = (self.success and num_tests_failed == 0)

        for queue_entry in self.queue_entries:
            if do_reboot:
                # don't pass the queue entry to the CleanupTask. if the cleanup
                # fails, the job doesn't care -- it's over.
                cleanup_task = CleanupTask(host=queue_entry.get_host())
                self.agent.dispatcher.add_agent(Agent([cleanup_task]))
            else:
                queue_entry.host.set_status('Ready')


    def epilog(self):
        super(QueueTask, self).epilog()
        self._finish_task(self.success)
        self._reboot_hosts()

        print "queue_task finished with succes=%s" % self.success


class RecoveryQueueTask(QueueTask):
    def __init__(self, job, queue_entries, run_monitor):
        super(RecoveryQueueTask, self).__init__(job, queue_entries, cmd=None)
        self.run_monitor = run_monitor


    def run(self):
        self.monitor = self.run_monitor


    def prolog(self):
        # recovering an existing process - don't do prolog
        pass


class CleanupTask(PreJobTask):
    def __init__(self, host=None, queue_entry=None):
        assert bool(host) ^ bool(queue_entry)
        if queue_entry:
            host = queue_entry.get_host()
        self.queue_entry = queue_entry
        self.host = host

        self.create_temp_resultsdir('.cleanup')
        self.cmd = [_autoserv_path, '-p', '--cleanup', '-m', host.hostname,
                    '-r', _drone_manager.absolute_path(self.temp_results_dir)]
        repair_task = RepairTask(host, queue_entry=queue_entry)
        super(CleanupTask, self).__init__(self.cmd, self.temp_results_dir,
                                          failure_tasks=[repair_task])

        self._set_ids(host=host, queue_entries=[queue_entry])
        self.set_host_log_file('cleanup', self.host)


    def prolog(self):
        super(CleanupTask, self).prolog()
        print "starting cleanup task for host: %s" % self.host.hostname
        self.host.set_status("Cleaning")


    def epilog(self):
        super(CleanupTask, self).epilog()
        if self.success:
            self.host.set_status('Ready')
            self.host.update_field('dirty', 0)


class AbortTask(AgentTask):
    def __init__(self, queue_entry, agents_to_abort):
        super(AbortTask, self).__init__('')
        self.queue_entry = queue_entry
        # don't use _set_ids, since we don't want to set the host_ids
        self.queue_entry_ids = [queue_entry.id]
        self.agents_to_abort = agents_to_abort


    def prolog(self):
        print "starting abort on host %s, job %s" % (
                self.queue_entry.host_id, self.queue_entry.job_id)


    def epilog(self):
        super(AbortTask, self).epilog()
        self.queue_entry.set_status('Aborted')
        self.success = True


    def run(self):
        for agent in self.agents_to_abort:
            if (agent.active_task):
                agent.active_task.abort()


class FinalReparseTask(AgentTask):
    _num_running_parses = 0

    def __init__(self, queue_entries):
        self._queue_entries = queue_entries
        # don't use _set_ids, since we don't want to set the host_ids
        self.queue_entry_ids = [entry.id for entry in queue_entries]
        self._parse_started = False

        assert len(queue_entries) > 0
        queue_entry = queue_entries[0]

        self._execution_tag = queue_entry.execution_tag()
        self._results_dir = _drone_manager.absolute_path(self._execution_tag)
        self._autoserv_monitor = PidfileRunMonitor()
        self._autoserv_monitor.attach_to_existing_process(self._execution_tag)
        self._final_status = self._determine_final_status()

        if _testing_mode:
            self.cmd = 'true'
        else:
            super(FinalReparseTask, self).__init__(
                cmd=self._generate_parse_command(),
                working_directory=self._execution_tag)

        self.log_file = os.path.join(self._execution_tag, '.parse.log')


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


    def _determine_final_status(self):
        # we'll use a PidfileRunMonitor to read the autoserv exit status
        if self._autoserv_monitor.exit_code() == 0:
            return models.HostQueueEntry.Status.COMPLETED
        return models.HostQueueEntry.Status.FAILED


    def prolog(self):
        super(FinalReparseTask, self).prolog()
        for queue_entry in self._queue_entries:
            queue_entry.set_status(models.HostQueueEntry.Status.PARSING)


    def epilog(self):
        super(FinalReparseTask, self).epilog()
        for queue_entry in self._queue_entries:
            queue_entry.set_status(self._final_status)


    def _generate_parse_command(self):
        return [_parser_path, '--write-pidfile', '-l', '2', '-r', '-o',
                self._results_dir]


    def poll(self):
        # override poll to keep trying to start until the parse count goes down
        # and we can, at which point we revert to default behavior
        if self._parse_started:
            super(FinalReparseTask, self).poll()
        else:
            self._try_starting_parse()


    def run(self):
        # override run() to not actually run unless we can
        self._try_starting_parse()


    def _try_starting_parse(self):
        if not self._can_run_new_parse():
            return

        # actually run the parse command
        self.monitor = PidfileRunMonitor()
        self.monitor.run(self.cmd, self._working_directory,
                         log_file=self.log_file,
                         pidfile_name='.parser_execute',
                         paired_with_pidfile=self._autoserv_monitor.pidfile_id)

        self._increment_running_parses()
        self._parse_started = True


    def finished(self, success):
        super(FinalReparseTask, self).finished(success)
        self._decrement_running_parses()


class DBObject(object):
    def __init__(self, id=None, row=None, new_record=False):
        assert (bool(id) != bool(row))

        self.__table = self._get_table()

        self.__new_record = new_record

        if row is None:
            sql = 'SELECT * FROM %s WHERE ID=%%s' % self.__table
            rows = _db.execute(sql, (id,))
            if len(rows) == 0:
                raise "row not found (table=%s, id=%s)" % \
                                        (self.__table, id)
            row = rows[0]

        self._update_fields_from_row(row)


    def _update_fields_from_row(self, row):
        assert len(row) == self.num_cols(), (
            "table = %s, row = %s/%d, fields = %s/%d" % (
            self.__table, row, len(row), self._fields(), self.num_cols()))

        self._valid_fields = set()
        for field, value in zip(self._fields(), row):
            setattr(self, field, value)
            self._valid_fields.add(field)

        self._valid_fields.remove('id')


    @classmethod
    def _get_table(cls):
        raise NotImplementedError('Subclasses must override this')


    @classmethod
    def _fields(cls):
        raise NotImplementedError('Subclasses must override this')


    @classmethod
    def num_cols(cls):
        return len(cls._fields())


    def count(self, where, table = None):
        if not table:
            table = self.__table

        rows = _db.execute("""
                SELECT count(*) FROM %s
                WHERE %s
        """ % (table, where))

        assert len(rows) == 1

        return int(rows[0][0])


    def update_field(self, field, value, condition=''):
        assert field in self._valid_fields

        if getattr(self, field) == value:
            return

        query = "UPDATE %s SET %s = %%s WHERE id = %%s" % (self.__table, field)
        if condition:
            query += ' AND (%s)' % condition
        _db.execute(query, (value, self.id))

        setattr(self, field, value)


    def save(self):
        if self.__new_record:
            keys = self._fields()[1:] # avoid id
            columns = ','.join([str(key) for key in keys])
            values = ['"%s"' % self.__dict__[key] for key in keys]
            values = ','.join(values)
            query = """INSERT INTO %s (%s) VALUES (%s)""" % \
                                    (self.__table, columns, values)
            _db.execute(query)


    def delete(self):
        query = 'DELETE FROM %s WHERE id=%%s' % self.__table
        _db.execute(query, (self.id,))


    @staticmethod
    def _prefix_with(string, prefix):
        if string:
            string = prefix + string
        return string


    @classmethod
    def fetch(cls, where='', params=(), joins='', order_by=''):
        order_by = cls._prefix_with(order_by, 'ORDER BY ')
        where = cls._prefix_with(where, 'WHERE ')
        query = ('SELECT %(table)s.* FROM %(table)s %(joins)s '
                 '%(where)s %(order_by)s' % {'table' : cls._get_table(),
                                             'joins' : joins,
                                             'where' : where,
                                             'order_by' : order_by})
        rows = _db.execute(query, params)
        for row in rows:
            yield cls(row=row)


class IneligibleHostQueue(DBObject):
    def __init__(self, id=None, row=None, new_record=None):
        super(IneligibleHostQueue, self).__init__(id=id, row=row,
                                                  new_record=new_record)


    @classmethod
    def _get_table(cls):
        return 'ineligible_host_queues'


    @classmethod
    def _fields(cls):
        return ['id', 'job_id', 'host_id']


class Label(DBObject):
    @classmethod
    def _get_table(cls):
        return 'labels'


    @classmethod
    def _fields(cls):
        return ['id', 'name', 'kernel_config', 'platform', 'invalid',
                'only_if_needed']


class Host(DBObject):
    def __init__(self, id=None, row=None):
        super(Host, self).__init__(id=id, row=row)


    @classmethod
    def _get_table(cls):
        return 'hosts'


    @classmethod
    def _fields(cls):
        return ['id', 'hostname', 'locked', 'synch_id','status',
                'invalid', 'protection', 'locked_by_id', 'lock_time', 'dirty']


    def current_task(self):
        rows = _db.execute("""
                SELECT * FROM host_queue_entries WHERE host_id=%s AND NOT complete AND active
                """, (self.id,))

        if len(rows) == 0:
            return None
        else:
            assert len(rows) == 1
            results = rows[0];
#           print "current = %s" % results
            return HostQueueEntry(row=results)


    def yield_work(self):
        print "%s yielding work" % self.hostname
        if self.current_task():
            self.current_task().requeue()

    def set_status(self,status):
        print '%s -> %s' % (self.hostname, status)
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
    def __init__(self, id=None, row=None):
        assert id or row
        super(HostQueueEntry, self).__init__(id=id, row=row)
        self.job = Job(self.job_id)

        if self.host_id:
            self.host = Host(self.host_id)
        else:
            self.host = None

        self.queue_log_path = os.path.join(self.job.tag(),
                                           'queue.log.' + str(self.id))


    @classmethod
    def _get_table(cls):
        return 'host_queue_entries'


    @classmethod
    def _fields(cls):
        return ['id', 'job_id', 'host_id', 'priority', 'status', 'meta_host',
                'active', 'complete', 'deleted', 'execution_subdir']


    def _view_job_url(self):
        return "%s#tab_id=view_job&object_id=%s" % (_base_url, self.job.id)


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
        print "creating block %s/%s" % (self.job.id, host_id)
        row = [0, self.job.id, host_id]
        block = IneligibleHostQueue(row=row, new_record=True)
        block.save()


    def unblock_host(self, host_id):
        print "removing block %s/%s" % (self.job.id, host_id)
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
        abort_statuses = ['Abort', 'Aborting', 'Aborted']
        if status not in abort_statuses:
            condition = ' AND '.join(['status <> "%s"' % x
                                      for x in abort_statuses])
        else:
            condition = ''
        self.update_field('status', status, condition=condition)

        print "%s -> %s" % (self, self.status)

        if status in ['Queued', 'Parsing']:
            self.update_field('complete', False)
            self.update_field('active', False)

        if status in ['Pending', 'Running', 'Verifying', 'Starting',
                      'Aborting']:
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


    def run(self,assigned_host=None):
        if self.meta_host:
            assert assigned_host
            # ensure results dir exists for the queue log
            self.set_host(assigned_host)

        print "%s/%s scheduled on %s, status=%s" % (self.job.name,
                        self.meta_host, self.host.hostname, self.status)

        return self.job.run(queue_entry=self)

    def requeue(self):
        self.set_status('Queued')
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


    def abort(self, dispatcher, agents_to_abort=[]):
        host = self.get_host()
        if self.active and host:
            dispatcher.add_agent(Agent(tasks=host.reverify_tasks()))

        abort_task = AbortTask(self, agents_to_abort)
        self.set_status('Aborting')
        dispatcher.add_agent(Agent(tasks=[abort_task], num_processes=0))

    def execution_tag(self):
        assert self.execution_subdir
        return "%s-%s/%s" % (self.job.id, self.job.owner, self.execution_subdir)


class Job(DBObject):
    def __init__(self, id=None, row=None):
        assert id or row
        super(Job, self).__init__(id=id, row=row)


    @classmethod
    def _get_table(cls):
        return 'jobs'


    @classmethod
    def _fields(cls):
        return  ['id', 'owner', 'name', 'priority', 'control_file',
                 'control_type', 'created_on', 'synch_count', 'timeout',
                 'run_verify', 'email_list', 'reboot_before', 'reboot_after']


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


    def _stop_all_entries(self, entries_to_abort):
        """
        queue_entries: sequence of models.HostQueueEntry objects
        """
        for child_entry in entries_to_abort:
            assert not child_entry.complete
            if child_entry.status == models.HostQueueEntry.Status.PENDING:
                child_entry.host.status = models.Host.Status.READY
                child_entry.host.save()
            child_entry.status = models.HostQueueEntry.Status.STOPPED
            child_entry.save()


    def stop_if_necessary(self):
        not_yet_run = models.HostQueueEntry.objects.filter(
            job=self.id, status__in=(models.HostQueueEntry.Status.QUEUED,
                                     models.HostQueueEntry.Status.VERIFYING,
                                     models.HostQueueEntry.Status.PENDING))
        if not_yet_run.count() < self.synch_count:
            self._stop_all_entries(not_yet_run)


    def write_to_machines_file(self, queue_entry):
        hostname = queue_entry.get_host().hostname
        file_path = os.path.join(self.tag(), '.machines')
        _drone_manager.write_lines_to_file(file_path, [hostname])


    def _next_group_name(self):
        query = models.HostQueueEntry.objects.filter(
            job=self.id).values('execution_subdir').distinct()
        subdirs = (entry['execution_subdir'] for entry in query)
        groups = (re.match(r'group(\d+)', subdir) for subdir in subdirs)
        ids = [int(match.group(1)) for match in groups if match]
        if ids:
            next_id = max(ids) + 1
        else:
            next_id = 0
        return "group%d" % next_id


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

        params = [_autoserv_path, '-P', execution_tag, '-p', '-n',
                  '-r', _drone_manager.absolute_path(execution_tag),
                  '-u', self.owner, '-l', self.name, '-m', hostnames,
                  _drone_manager.absolute_path(control_path)]

        if not self.is_server_job():
            params.append('-c')

        return params


    def _get_pre_job_tasks(self, queue_entry):
        do_reboot = False
        if self.reboot_before == models.RebootBefore.ALWAYS:
            do_reboot = True
        elif self.reboot_before == models.RebootBefore.IF_DIRTY:
            do_reboot = queue_entry.get_host().dirty

        tasks = []
        if do_reboot:
            tasks.append(CleanupTask(queue_entry=queue_entry))
        tasks.append(VerifyTask(queue_entry=queue_entry))
        return tasks


    def _assign_new_group(self, queue_entries):
        if len(queue_entries) == 1:
            group_name = queue_entries[0].get_host().hostname
        else:
            group_name = self._next_group_name()
            print 'Running synchronous job %d hosts %s as %s' % (
                self.id, [entry.host.hostname for entry in queue_entries],
                group_name)

        for queue_entry in queue_entries:
            queue_entry.set_execution_subdir(group_name)


    def _choose_group_to_run(self, include_queue_entry):
        chosen_entries = [include_queue_entry]

        num_entries_needed = self.synch_count - 1
        if num_entries_needed > 0:
            pending_entries = HostQueueEntry.fetch(
                where='job_id = %s AND status = "Pending" AND id != %s',
                params=(self.id, include_queue_entry.id))
            chosen_entries += list(pending_entries)[:num_entries_needed]

        self._assign_new_group(chosen_entries)
        return chosen_entries


    def run(self, queue_entry):
        if not self.is_ready():
            if self.run_verify:
                queue_entry.set_status(models.HostQueueEntry.Status.VERIFYING)
                return Agent(self._get_pre_job_tasks(queue_entry))
            else:
                return queue_entry.on_pending()

        queue_entries = self._choose_group_to_run(queue_entry)
        return self._finish_run(queue_entries)


    def _finish_run(self, queue_entries, initial_tasks=[]):
        for queue_entry in queue_entries:
            queue_entry.set_status('Starting')
        params = self._get_autoserv_params(queue_entries)
        queue_task = QueueTask(job=self, queue_entries=queue_entries,
                               cmd=params)
        tasks = initial_tasks + [queue_task]
        entry_ids = [entry.id for entry in queue_entries]

        return Agent(tasks, num_processes=len(queue_entries))


if __name__ == '__main__':
    main()
