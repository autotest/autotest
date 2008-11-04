#!/usr/bin/python -u

"""
Autotest scheduler
"""


import datetime, errno, MySQLdb, optparse, os, pwd, Queue, re, shutil, signal
import smtplib, socket, stat, subprocess, sys, tempfile, time, traceback
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import host_protections, utils
from autotest_lib.database import database_connection
from autotest_lib.frontend.afe import models


RESULTS_DIR = '.'
AUTOSERV_NICE_LEVEL = 10
CONFIG_SECTION = 'AUTOTEST_WEB'

AUTOTEST_PATH = os.path.join(os.path.dirname(__file__), '..')

if os.environ.has_key('AUTOTEST_DIR'):
    AUTOTEST_PATH = os.environ['AUTOTEST_DIR']
AUTOTEST_SERVER_DIR = os.path.join(AUTOTEST_PATH, 'server')
AUTOTEST_TKO_DIR = os.path.join(AUTOTEST_PATH, 'tko')

if AUTOTEST_SERVER_DIR not in sys.path:
    sys.path.insert(0, AUTOTEST_SERVER_DIR)

AUTOSERV_PID_FILE = '.autoserv_execute'
# how long to wait for autoserv to write a pidfile
PIDFILE_TIMEOUT = 5 * 60 # 5 min

_db = None
_shutdown = False
_notify_email = None
_autoserv_path = 'autoserv'
_testing_mode = False
_global_config_section = 'SCHEDULER'
_base_url = None
# see os.getlogin() online docs
_email_from = pwd.getpwuid(os.getuid())[0]


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

    # read in notify_email from global_config
    c = global_config.global_config
    global _notify_email
    val = c.get_config_value(_global_config_section, "notify_email")
    if val != "":
        _notify_email = val

    tick_pause = c.get_config_value(
        _global_config_section, 'tick_pause_sec', type=int)

    if options.test:
        global _autoserv_path
        _autoserv_path = 'autoserv_dummy'
        global _testing_mode
        _testing_mode = True

    # read in base url
    global _base_url
    val = c.get_config_value(CONFIG_SECTION, "base_url")
    if val:
        _base_url = val
    else:
        _base_url = "http://your_autotest_server/afe/"

    init(options.logfile)
    dispatcher = Dispatcher()
    dispatcher.do_initial_recovery(recover_hosts=options.recover_hosts)

    try:
        while not _shutdown:
            dispatcher.tick()
            time.sleep(tick_pause)
    except:
        log_stacktrace("Uncaught exception; terminating monitor_db")

    email_manager.send_queued_emails()
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
            CONFIG_SECTION, 'database', 'stresstest_autotest_web')

    os.environ['PATH'] = AUTOTEST_SERVER_DIR + ':' + os.environ['PATH']
    global _db
    _db = database_connection.DatabaseConnection(CONFIG_SECTION)
    _db.connect()

    # ensure Django connection is in autocommit
    setup_django_environment.enable_autocommit()

    print "Setting signal handler"
    signal.signal(signal.SIGINT, handle_sigint)

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

def remove_file_or_dir(path):
    if stat.S_ISDIR(os.stat(path).st_mode):
        # directory
        shutil.rmtree(path)
    else:
        # file
        os.remove(path)


def log_stacktrace(reason):
    (type, value, tb) = sys.exc_info()
    str = "EXCEPTION: %s\n" % reason
    str += ''.join(traceback.format_exception(type, value, tb))

    sys.stderr.write("\n%s\n" % str)
    email_manager.enqueue_notify_email("monitor_db exception", str)


def get_proc_poll_fn(pid):
    proc_path = os.path.join('/proc', str(pid))
    def poll_fn():
        if os.path.exists(proc_path):
            return None
        return 0 # we can't get a real exit code
    return poll_fn


def send_email(from_addr, to_string, subject, body):
    """Mails out emails to the addresses listed in to_string.

    to_string is split into a list which can be delimited by any of:
            ';', ',', ':' or any whitespace
    """

    # Create list from string removing empty strings from the list.
    to_list = [x for x in re.split('\s|,|;|:', to_string) if x]
    if not to_list:
        return

    msg = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (
        from_addr, ', '.join(to_list), subject, body)
    try:
        mailer = smtplib.SMTP('localhost')
        try:
            mailer.sendmail(from_addr, to_list, msg)
        finally:
            mailer.quit()
    except Exception, e:
        print "Sending email failed. Reason: %s" % repr(e)


def kill_autoserv(pid, poll_fn=None):
    print 'killing', pid
    if poll_fn is None:
        poll_fn = get_proc_poll_fn(pid)
    if poll_fn() == None:
        os.kill(pid, signal.SIGCONT)
        os.kill(pid, signal.SIGTERM)


class EmailNotificationManager(object):
    def __init__(self):
        self._emails = []

    def enqueue_notify_email(self, subject, message):
        if not _notify_email:
            return

        body = 'Subject: ' + subject + '\n'
        body += "%s / %s / %s\n%s" % (socket.gethostname(),
                                      os.getpid(),
                                      time.strftime("%X %x"), message)
        self._emails.append(body)


    def send_queued_emails(self):
        if not self._emails:
            return
        subject = 'Scheduler notifications from ' + socket.gethostname()
        separator = '\n' + '-' * 40 + '\n'
        body = separator.join(self._emails)

        send_email(_email_from, _notify_email, subject, body)
        self._emails = []

email_manager = EmailNotificationManager()


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


class Dispatcher:
    autoserv_procs_cache = None
    max_running_processes = global_config.global_config.get_config_value(
        _global_config_section, 'max_running_jobs', type=int)
    max_processes_started_per_cycle = (
        global_config.global_config.get_config_value(
            _global_config_section, 'max_jobs_started_per_cycle', type=int))
    clean_interval = (
        global_config.global_config.get_config_value(
            _global_config_section, 'clean_interval_minutes', type=int))
    synch_job_start_timeout_minutes = (
        global_config.global_config.get_config_value(
            _global_config_section, 'synch_job_start_timeout_minutes',
            type=int))

    def __init__(self):
        self._agents = []
        self._last_clean_time = time.time()
        self._host_scheduler = HostScheduler()


    def do_initial_recovery(self, recover_hosts=True):
        # always recover processes
        self._recover_processes()

        if recover_hosts:
            self._recover_hosts()


    def tick(self):
        Dispatcher.autoserv_procs_cache = None
        self._run_cleanup_maybe()
        self._find_aborting()
        self._schedule_new_jobs()
        self._handle_agents()
        email_manager.send_queued_emails()


    def _run_cleanup_maybe(self):
        if self._last_clean_time + self.clean_interval * 60 < time.time():
            print 'Running cleanup'
            self._abort_timed_out_jobs()
            self._abort_jobs_past_synch_start_timeout()
            self._clear_inactive_blocks()
            self._check_for_db_inconsistencies()
            self._last_clean_time = time.time()


    def add_agent(self, agent):
        self._agents.append(agent)
        agent.dispatcher = self

    # Find agent corresponding to the specified queue_entry
    def get_agents(self, queue_entry):
        res_agents = []
        for agent in self._agents:
            if queue_entry.id in agent.queue_entry_ids:
                res_agents.append(agent)
        return res_agents


    def remove_agent(self, agent):
        self._agents.remove(agent)


    def num_running_processes(self):
        return sum(agent.num_processes for agent in self._agents
                   if agent.is_running())


    @classmethod
    def find_autoservs(cls, orphans_only=False):
        """\
        Returns a dict mapping pids to command lines for root autoserv
        processes.  If orphans_only=True, return only processes that
        have been orphaned (i.e. parent pid = 1).
        """
        if cls.autoserv_procs_cache is not None:
            return cls.autoserv_procs_cache

        proc = subprocess.Popen(
            ['/bin/ps', 'x', '-o', 'pid,pgid,ppid,comm,args'],
            stdout=subprocess.PIPE)
        # split each line into the four columns output by ps
        procs = [line.split(None, 4) for line in
                 proc.communicate()[0].splitlines()]
        autoserv_procs = {}
        for proc in procs:
            # check ppid == 1 for orphans
            if orphans_only and proc[2] != 1:
                continue
            # only root autoserv processes have pgid == pid
            if (proc[3] == 'autoserv' and   # comm
                proc[1] == proc[0]):        # pgid == pid
                # map pid to args
                autoserv_procs[int(proc[0])] = proc[4]
        cls.autoserv_procs_cache = autoserv_procs
        return autoserv_procs


    def recover_queue_entry(self, queue_entry, run_monitor):
        job = queue_entry.job
        if job.is_synchronous():
            all_queue_entries = job.get_host_queue_entries()
        else:
            all_queue_entries = [queue_entry]
        all_queue_entry_ids = [queue_entry.id for queue_entry
                               in all_queue_entries]
        queue_task = RecoveryQueueTask(
            job=queue_entry.job,
            queue_entries=all_queue_entries,
            run_monitor=run_monitor)
        self.add_agent(Agent(tasks=[queue_task],
                             queue_entry_ids=all_queue_entry_ids))


    def _recover_processes(self):
        orphans = self.find_autoservs(orphans_only=True)

        # first, recover running queue entries
        rows = _db.execute("""SELECT * FROM host_queue_entries
                              WHERE status = 'Running'""")
        queue_entries = [HostQueueEntry(row=i) for i in rows]
        requeue_entries = []
        recovered_entry_ids = set()
        for queue_entry in queue_entries:
            run_monitor = PidfileRunMonitor(
                queue_entry.results_dir())
            if not run_monitor.has_pid():
                # autoserv apparently never got run, so requeue
                requeue_entries.append(queue_entry)
                continue
            if queue_entry.id in recovered_entry_ids:
                # synchronous job we've already recovered
                continue
            pid = run_monitor.get_pid()
            print 'Recovering queue entry %d (pid %d)' % (
                queue_entry.id, pid)
            job = queue_entry.job
            if job.is_synchronous():
                for entry in job.get_host_queue_entries():
                    assert entry.active
                    recovered_entry_ids.add(entry.id)
            self.recover_queue_entry(queue_entry,
                                     run_monitor)
            orphans.pop(pid, None)

        # and requeue other active queue entries
        rows = _db.execute("""SELECT * FROM host_queue_entries
                              WHERE active AND NOT complete
                              AND status != 'Running'
                              AND status != 'Pending'
                              AND status != 'Abort'
                              AND status != 'Aborting'""")
        queue_entries = [HostQueueEntry(row=i) for i in rows]
        for queue_entry in queue_entries + requeue_entries:
            print 'Requeuing running QE %d' % queue_entry.id
            queue_entry.clear_results_dir(dont_delete_files=True)
            queue_entry.requeue()


        # now kill any remaining autoserv processes
        for pid in orphans.keys():
            print 'Killing orphan %d (%s)' % (pid, orphans[pid])
            kill_autoserv(pid)

        # recover aborting tasks
        rebooting_host_ids = set()
        rows = _db.execute("""SELECT * FROM host_queue_entries
                           WHERE status='Abort' or status='Aborting'""")
        queue_entries = [HostQueueEntry(row=i) for i in rows]
        for queue_entry in queue_entries:
            print 'Recovering aborting QE %d' % queue_entry.id
            agent = queue_entry.abort()
            self.add_agent(agent)
            if queue_entry.get_host():
                rebooting_host_ids.add(queue_entry.get_host().id)

        self._recover_parsing_entries()

        # reverify hosts that were in the middle of verify, repair or
        # reboot
        self._reverify_hosts_where("""(status = 'Repairing' OR
                                       status = 'Verifying' OR
                                       status = 'Rebooting')""",
                                   exclude_ids=rebooting_host_ids)

        # finally, recover "Running" hosts with no active queue entries,
        # although this should never happen
        message = ('Recovering running host %s - this probably '
                   'indicates a scheduler bug')
        self._reverify_hosts_where("""status = 'Running' AND
                                      id NOT IN (SELECT host_id
                                                 FROM host_queue_entries
                                                 WHERE active)""",
                                   print_message=message)


    def _reverify_hosts_where(self, where,
                              print_message='Reverifying host %s',
                              exclude_ids=set()):
        rows = _db.execute('SELECT * FROM hosts WHERE locked = 0 AND '
                           'invalid = 0 AND ' + where)
        hosts = [Host(row=i) for i in rows]
        for host in hosts:
            if host.id in exclude_ids:
                continue
            if print_message is not None:
                print print_message % host.hostname
            verify_task = VerifyTask(host = host)
            self.add_agent(Agent(tasks = [verify_task]))


    def _recover_parsing_entries(self):
        # make sure there are no old parsers running
        os.system('killall parse')

        recovered_synch_jobs = set()
        for entry in HostQueueEntry.fetch(where='status = "Parsing"'):
            job = entry.job
            if job.is_synchronous():
                if job.id in recovered_synch_jobs:
                    continue
                queue_entries = job.get_host_queue_entries()
                recovered_synch_jobs.add(job.id)
            else:
                queue_entries = [entry]

            reparse_task = FinalReparseTask(queue_entries)
            self.add_agent(Agent([reparse_task]))


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
            minutes=self.synch_job_start_timeout_minutes)
        timeout_start = datetime.datetime.now() - timeout_delta
        query = models.Job.objects.filter(
            synch_type=models.Test.SynchType.SYNCHRONOUS,
            created_on__lt=timeout_start,
            hostqueueentry__status='Pending',
            hostqueueentry__host__acl_group__name='Everyone')
        for job in query.distinct():
            print 'Aborting job %d due to start timeout' % job.id
            job.abort(None)


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
            where='NOT complete AND NOT active',
            order_by='priority DESC, meta_host, job_id'))


    def _schedule_new_jobs(self):
        print "finding work"

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
        # in some cases (synchronous jobs with run_verify=False), agent may be None
        if agent:
            self.add_agent(agent)


    def _find_aborting(self):
        num_aborted = 0
        # Find jobs that are aborting
        for entry in queue_entries_to_abort():
            agents_to_abort = self.get_agents(entry)
            for agent in agents_to_abort:
                self.remove_agent(agent)

            agent = entry.abort(agents_to_abort)
            self.add_agent(agent)
            num_aborted += 1
            if num_aborted >= 50:
                break


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
            self.max_running_processes):
            return False
        # if a single agent exceeds the per-cycle throttling, still allow it to
        # run when it's the first agent in the cycle
        if num_started_this_cycle == 0:
            return True
        # per-cycle throttling
        if (num_started_this_cycle + agent.num_processes >
            self.max_processes_started_per_cycle):
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
                self._agents.remove(agent)
                num_running_processes -= agent.num_processes
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
            email_manager.enqueue_notify_email(subject, message)


class RunMonitor(object):
    def __init__(self, cmd, nice_level = None, log_file = None):
        self.nice_level = nice_level
        self.log_file = log_file
        self.cmd = cmd

    def run(self):
        if self.nice_level:
            nice_cmd = ['nice','-n', str(self.nice_level)]
            nice_cmd.extend(self.cmd)
            self.cmd = nice_cmd

        out_file = None
        if self.log_file:
            try:
                os.makedirs(os.path.dirname(self.log_file))
            except OSError, exc:
                if exc.errno != errno.EEXIST:
                    log_stacktrace(
                        'Unexpected error creating logfile '
                        'directory for %s' % self.log_file)
            try:
                out_file = open(self.log_file, 'a')
                out_file.write("\n%s\n" % ('*'*80))
                out_file.write("%s> %s\n" %
                               (time.strftime("%X %x"),
                                self.cmd))
                out_file.write("%s\n" % ('*'*80))
            except (OSError, IOError):
                log_stacktrace('Error opening log file %s' %
                               self.log_file)

        if not out_file:
            out_file = open('/dev/null', 'w')

        in_devnull = open('/dev/null', 'r')
        print "cmd = %s" % self.cmd
        print "path = %s" % os.getcwd()

        self.proc = subprocess.Popen(self.cmd, stdout=out_file,
                                     stderr=subprocess.STDOUT,
                                     stdin=in_devnull)
        out_file.close()
        in_devnull.close()


    def get_pid(self):
        return self.proc.pid


    def kill(self):
        kill_autoserv(self.get_pid(), self.exit_code)


    def exit_code(self):
        return self.proc.poll()


class PidfileException(Exception):
    """\
    Raised when there's some unexpected behavior with the pid file.
    """


class PidfileRunMonitor(RunMonitor):
    class PidfileState(object):
        pid = None
        exit_status = None
        num_tests_failed = None

        def reset(self):
            self.pid = self.exit_status = self.all_tests_passed = None


    def __init__(self, results_dir, cmd=None, nice_level=None,
                 log_file=None):
        self.results_dir = os.path.abspath(results_dir)
        self.pid_file = os.path.join(results_dir, AUTOSERV_PID_FILE)
        self.lost_process = False
        self.start_time = time.time()
        self._state = self.PidfileState()
        super(PidfileRunMonitor, self).__init__(cmd, nice_level, log_file)


    def has_pid(self):
        self._get_pidfile_info()
        return self._state.pid is not None


    def get_pid(self):
        self._get_pidfile_info()
        assert self._state.pid is not None
        return self._state.pid


    def _check_command_line(self, command_line, spacer=' ',
                            print_error=False):
        results_dir_arg = spacer.join(('', '-r', self.results_dir, ''))
        match = results_dir_arg in command_line
        if print_error and not match:
            print '%s not found in %s' % (repr(results_dir_arg),
                                          repr(command_line))
        return match


    def _check_proc_fs(self):
        cmdline_path = os.path.join('/proc', str(self._state.pid), 'cmdline')
        try:
            cmdline_file = open(cmdline_path, 'r')
            cmdline = cmdline_file.read().strip()
            cmdline_file.close()
        except IOError:
            return False
        # /proc/.../cmdline has \x00 separating args
        return self._check_command_line(cmdline, spacer='\x00',
                                        print_error=True)


    def _read_pidfile(self):
        self._state.reset()
        if not os.path.exists(self.pid_file):
            return
        file_obj = open(self.pid_file, 'r')
        lines = file_obj.readlines()
        file_obj.close()
        if not lines:
            return
        if len(lines) > 3:
            raise PidfileException('Corrupt pid file (%d lines) at %s:\n%s' %
                                   (len(lines), self.pid_file, lines))
        try:
            self._state.pid = int(lines[0])
            if len(lines) > 1:
                self._state.exit_status = int(lines[1])
                if len(lines) == 3:
                    self._state.num_tests_failed = int(lines[2])
                else:
                    # maintain backwards-compatibility with two-line pidfiles
                    self._state.num_tests_failed = 0
        except ValueError, exc:
            raise PidfileException('Corrupt pid file: ' + str(exc.args))


    def _find_autoserv_proc(self):
        autoserv_procs = Dispatcher.find_autoservs()
        for pid, args in autoserv_procs.iteritems():
            if self._check_command_line(args):
                return pid, args
        return None, None


    def _handle_pidfile_error(self, error, message=''):
        message = error + '\nPid: %s\nPidfile: %s\n%s' % (self._state.pid,
                                                          self.pid_file,
                                                          message)
        print message
        email_manager.enqueue_notify_email(error, message)
        if self._state.pid is not None:
            pid = self._state.pid
        else:
            pid = 0
        self.on_lost_process(pid)


    def _get_pidfile_info_helper(self):
        if self.lost_process:
            return

        self._read_pidfile()

        if self._state.pid is None:
            self._handle_no_pid()
            return

        if self._state.exit_status is None:
            # double check whether or not autoserv is running
            proc_running = self._check_proc_fs()
            if proc_running:
                return

            # pid but no process - maybe process *just* exited
            self._read_pidfile()
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
        except PidfileException, exc:
            self._handle_pidfile_error('Pidfile error', traceback.format_exc())


    def _handle_no_pid(self):
        """\
        Called when no pidfile is found or no pid is in the pidfile.
        """
        # is autoserv running?
        pid, args = self._find_autoserv_proc()
        if pid is None:
            # no autoserv process running
            message = 'No pid found at ' + self.pid_file
        else:
            message = ("Process %d (%s) hasn't written pidfile %s" %
                       (pid, args, self.pid_file))

        print message
        if time.time() - self.start_time > PIDFILE_TIMEOUT:
            email_manager.enqueue_notify_email(
                'Process has failed to write pidfile', message)
            if pid is not None:
                kill_autoserv(pid)
            else:
                pid = 0
            self.on_lost_process(pid)
            return


    def on_lost_process(self, pid):
        """\
        Called when autoserv has exited without writing an exit status,
        or we've timed out waiting for autoserv to write a pid to the
        pidfile.  In either case, we just return failure and the caller
        should signal some kind of warning.

        pid is unimportant here, as it shouldn't be used by anyone.
        """
        self.lost_process = True
        self._state.pid = pid
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
    def __init__(self, tasks, queue_entry_ids=[], num_processes=1):
        self.active_task = None
        self.queue = Queue.Queue(0)
        self.dispatcher = None
        self.queue_entry_ids = queue_entry_ids
        self.num_processes = num_processes

        for task in tasks:
            self.add_task(task)


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
        return self.active_task == None and self.queue.empty()


    def start(self):
        assert self.dispatcher

        self._next_task()


class AgentTask(object):
    def __init__(self, cmd, failure_tasks = []):
        self.done = False
        self.failure_tasks = failure_tasks
        self.started = False
        self.cmd = cmd
        self.task = None
        self.agent = None
        self.monitor = None
        self.success = None


    def poll(self):
        print "poll"
        if self.monitor:
            self.tick(self.monitor.exit_code())
        else:
            self.finished(False)


    def tick(self, exit_code):
        if exit_code==None:
            return
#               print "exit_code was %d" % exit_code
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
        self.temp_results_dir = tempfile.mkdtemp(suffix=suffix)


    def cleanup(self):
        if (hasattr(self, 'temp_results_dir') and
            os.path.exists(self.temp_results_dir)):
            shutil.rmtree(self.temp_results_dir)


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


    def run(self):
        if self.cmd:
            print "agent starting monitor"
            log_file = None
            if hasattr(self, 'log_file'):
                log_file = self.log_file
            elif hasattr(self, 'host'):
                log_file = os.path.join(RESULTS_DIR, 'hosts',
                                        self.host.hostname)
            self.monitor = RunMonitor(
                self.cmd, nice_level=AUTOSERV_NICE_LEVEL, log_file=log_file)
            self.monitor.run()


class RepairTask(AgentTask):
    def __init__(self, host, fail_queue_entry=None):
        """\
        fail_queue_entry: queue entry to mark failed if this repair
        fails.
        """
        protection = host_protections.Protection.get_string(host.protection)
        # normalize the protection name
        protection = host_protections.Protection.get_attr_name(protection)
        self.create_temp_resultsdir('.repair')
        cmd = [_autoserv_path , '-R', '-m', host.hostname,
               '-r', self.temp_results_dir, '--host-protection', protection]
        self.host = host
        self.fail_queue_entry = fail_queue_entry
        super(RepairTask, self).__init__(cmd)


    def prolog(self):
        print "repair_task starting"
        self.host.set_status('Repairing')


    def epilog(self):
        super(RepairTask, self).epilog()
        if self.success:
            self.host.set_status('Ready')
        else:
            self.host.set_status('Repair Failed')
            if self.fail_queue_entry:
                self.fail_queue_entry.handle_host_failure()


class VerifyTask(AgentTask):
    def __init__(self, queue_entry=None, host=None):
        assert bool(queue_entry) != bool(host)

        self.host = host or queue_entry.host
        self.queue_entry = queue_entry

        self.create_temp_resultsdir('.verify')

        cmd = [_autoserv_path,'-v','-m',self.host.hostname, '-r', self.temp_results_dir]

        fail_queue_entry = None
        if queue_entry and not queue_entry.meta_host:
            fail_queue_entry = queue_entry
        failure_tasks = [RepairTask(self.host, fail_queue_entry)]

        super(VerifyTask, self).__init__(cmd,
                                         failure_tasks=failure_tasks)


    def prolog(self):
        print "starting verify on %s" % (self.host.hostname)
        if self.queue_entry:
            self.queue_entry.set_status('Verifying')
            self.queue_entry.clear_results_dir(
                self.queue_entry.verify_results_dir())
        self.host.set_status('Verifying')


    def cleanup(self):
        if not os.path.exists(self.temp_results_dir):
            return
        if self.queue_entry and (self.success or
                                 not self.queue_entry.meta_host):
            self.move_results()
        super(VerifyTask, self).cleanup()


    def epilog(self):
        super(VerifyTask, self).epilog()

        if self.success:
            self.host.set_status('Ready')
        elif self.queue_entry:
            self.queue_entry.requeue()


    def move_results(self):
        assert self.queue_entry is not None
        target_dir = self.queue_entry.verify_results_dir()
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        files = os.listdir(self.temp_results_dir)
        for filename in files:
            if filename == AUTOSERV_PID_FILE:
                continue
            self.force_move(os.path.join(self.temp_results_dir,
                                         filename),
                            os.path.join(target_dir, filename))


    @staticmethod
    def force_move(source, dest):
        """\
        Replacement for shutil.move() that will delete the destination
        if it exists, even if it's a directory.
        """
        if os.path.exists(dest):
            warning = 'Warning: removing existing destination file ' + dest
            print warning
            email_manager.enqueue_notify_email(warning, warning)
            remove_file_or_dir(dest)
        shutil.move(source, dest)


class VerifySynchronousTask(VerifyTask):
    def epilog(self):
        super(VerifySynchronousTask, self).epilog()
        if self.success:
            if self.queue_entry.job.num_complete() > 0:
                # some other entry failed verify, and we've
                # already been marked as stopped
                return

            agent = self.queue_entry.on_pending()
            if agent:
                self.agent.dispatcher.add_agent(agent)


class QueueTask(AgentTask):
    def __init__(self, job, queue_entries, cmd):
        super(QueueTask, self).__init__(cmd)
        self.job = job
        self.queue_entries = queue_entries


    @staticmethod
    def _write_keyval(keyval_dir, field, value, keyval_filename='keyval'):
        key_path = os.path.join(keyval_dir, keyval_filename)
        keyval_file = open(key_path, 'a')
        print >> keyval_file, '%s=%s' % (field, str(value))
        keyval_file.close()


    def _host_keyval_dir(self):
        return os.path.join(self.results_dir(), 'host_keyvals')


    def _write_host_keyval(self, host):
        labels = ','.join(host.labels())
        self._write_keyval(self._host_keyval_dir(), 'labels', labels,
                           keyval_filename=host.hostname)

    def _create_host_keyval_dir(self):
        directory = self._host_keyval_dir()
        if not os.path.exists(directory):
            os.makedirs(directory)


    def results_dir(self):
        return self.queue_entries[0].results_dir()


    def run(self):
        """\
        Override AgentTask.run() so we can use a PidfileRunMonitor.
        """
        self.monitor = PidfileRunMonitor(self.results_dir(),
                                         cmd=self.cmd,
                                         nice_level=AUTOSERV_NICE_LEVEL)
        self.monitor.run()


    def prolog(self):
        # write some job timestamps into the job keyval file
        queued = time.mktime(self.job.created_on.timetuple())
        started = time.time()
        self._write_keyval(self.results_dir(), "job_queued", int(queued))
        self._write_keyval(self.results_dir(), "job_started", int(started))
        self._create_host_keyval_dir()
        for queue_entry in self.queue_entries:
            self._write_host_keyval(queue_entry.host)
            print "starting queue_task on %s/%s" % (queue_entry.host.hostname, queue_entry.id)
            queue_entry.set_status('Running')
            queue_entry.host.set_status('Running')
            queue_entry.host.update_field('dirty', 1)
        if (not self.job.is_synchronous() and
            self.job.num_machines() > 1):
            assert len(self.queue_entries) == 1
            self.job.write_to_machines_file(self.queue_entries[0])


    def _finish_task(self, success):
        # write out the finished time into the results keyval
        finished = time.time()
        self._write_keyval(self.results_dir(), "job_finished", int(finished))

        # parse the results of the job
        reparse_task = FinalReparseTask(self.queue_entries)
        self.agent.dispatcher.add_agent(Agent([reparse_task]))


    def _log_abort(self):
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
            results_dir = self.results_dir()
            self._write_keyval(results_dir, "aborted_by", aborted_by.pop())
            self._write_keyval(results_dir, "aborted_on", max(aborted_on))


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

        if do_reboot:
            for queue_entry in self.queue_entries:
                # don't pass the queue entry to the RebootTask. if the reboot
                # fails, the job doesn't care -- it's over.
                reboot_task = RebootTask(host=queue_entry.get_host())
                self.agent.dispatcher.add_agent(Agent([reboot_task]))


    def epilog(self):
        super(QueueTask, self).epilog()
        for queue_entry in self.queue_entries:
            # set status to PARSING here so queue entry is marked complete
            queue_entry.set_status(models.HostQueueEntry.Status.PARSING)
            queue_entry.host.set_status('Ready')

        self._finish_task(self.success)
        self._reboot_hosts()

        print "queue_task finished with succes=%s" % self.success


class RecoveryQueueTask(QueueTask):
    def __init__(self, job, queue_entries, run_monitor):
        super(RecoveryQueueTask, self).__init__(job,
                                         queue_entries, cmd=None)
        self.run_monitor = run_monitor


    def run(self):
        self.monitor = self.run_monitor


    def prolog(self):
        # recovering an existing process - don't do prolog
        pass


class RebootTask(AgentTask):
    def __init__(self, host=None, queue_entry=None):
        assert bool(host) ^ bool(queue_entry)
        if queue_entry:
            host = queue_entry.get_host()

        # Current implementation of autoserv requires control file
        # to be passed on reboot action request. TODO: remove when no
        # longer appropriate.
        self.create_temp_resultsdir('.reboot')
        self.cmd = [_autoserv_path, '-b', '-m', host.hostname,
                    '-r', self.temp_results_dir, '/dev/null']
        self.queue_entry = queue_entry
        self.host = host
        repair_task = RepairTask(host, fail_queue_entry=queue_entry)
        super(RebootTask, self).__init__(self.cmd, failure_tasks=[repair_task])


    def prolog(self):
        print "starting reboot task for host: %s" % self.host.hostname
        self.host.set_status("Rebooting")


    def epilog(self):
        super(RebootTask, self).epilog()
        if self.success:
            self.host.set_status('Ready')
            self.host.update_field('dirty', 0)
        elif self.queue_entry:
            self.queue_entry.requeue()


class AbortTask(AgentTask):
    def __init__(self, queue_entry, agents_to_abort):
        self.queue_entry = queue_entry
        self.agents_to_abort = agents_to_abort
        super(AbortTask, self).__init__('')


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
    MAX_PARSE_PROCESSES = (
        global_config.global_config.get_config_value(
            _global_config_section, 'max_parse_processes', type=int))
    _num_running_parses = 0

    def __init__(self, queue_entries):
        self._queue_entries = queue_entries
        self._parse_started = False

        assert len(queue_entries) > 0
        queue_entry = queue_entries[0]
        job = queue_entry.job

        flags = []
        if job.is_synchronous():
            assert len(queue_entries) == job.num_machines()
        else:
            assert len(queue_entries) == 1
            if job.num_machines() > 1:
                flags = ['-l', '2']

        if _testing_mode:
            self.cmd = 'true'
            return

        self._results_dir = queue_entry.results_dir()
        self.log_file = os.path.abspath(os.path.join(self._results_dir,
                                                     '.parse.log'))
        super(FinalReparseTask, self).__init__(
            cmd=self.generate_parse_command(flags=flags))


    @classmethod
    def _increment_running_parses(cls):
        cls._num_running_parses += 1


    @classmethod
    def _decrement_running_parses(cls):
        cls._num_running_parses -= 1


    @classmethod
    def _can_run_new_parse(cls):
        return cls._num_running_parses < cls.MAX_PARSE_PROCESSES


    def prolog(self):
        super(FinalReparseTask, self).prolog()
        for queue_entry in self._queue_entries:
            queue_entry.set_status(models.HostQueueEntry.Status.PARSING)


    def epilog(self):
        super(FinalReparseTask, self).epilog()
        final_status = self._determine_final_status()
        for queue_entry in self._queue_entries:
            queue_entry.set_status(final_status)


    def _determine_final_status(self):
        # use a PidfileRunMonitor to read the autoserv exit status
        monitor = PidfileRunMonitor(self._results_dir)
        if monitor.exit_code() == 0:
            return models.HostQueueEntry.Status.COMPLETED
        return models.HostQueueEntry.Status.FAILED


    def generate_parse_command(self, flags=[]):
        parse = os.path.abspath(os.path.join(AUTOTEST_TKO_DIR, 'parse'))
        return [parse] + flags + ['-r', '-o', self._results_dir]


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
        super(FinalReparseTask, self).run()
        self._increment_running_parses()
        self._parse_started = True


    def finished(self, success):
        super(FinalReparseTask, self).finished(success)
        self._decrement_running_parses()


class DBObject(object):
    def __init__(self, id=None, row=None, new_record=False):
        assert (bool(id) != bool(row))

        self.__table = self._get_table()
        fields = self._fields()

        self.__new_record = new_record

        if row is None:
            sql = 'SELECT * FROM %s WHERE ID=%%s' % self.__table
            rows = _db.execute(sql, (id,))
            if len(rows) == 0:
                raise "row not found (table=%s, id=%s)" % \
                                        (self.__table, id)
            row = rows[0]

        assert len(row) == self.num_cols(), (
            "table = %s, row = %s/%d, fields = %s/%d" % (
            self.__table, row, len(row), fields, self.num_cols()))

        self.__valid_fields = {}
        for i,value in enumerate(row):
            self.__dict__[fields[i]] = value
            self.__valid_fields[fields[i]] = True

        del self.__valid_fields['id']


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
        assert self.__valid_fields[field]

        if self.__dict__[field] == value:
            return

        query = "UPDATE %s SET %s = %%s WHERE id = %%s" % (self.__table, field)
        if condition:
            query += ' AND (%s)' % condition
        _db.execute(query, (value, self.id))

        self.__dict__[field] = value


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


    def labels(self):
        """
        Fetch a list of names of all non-platform labels associated with this
        host.
        """
        rows = _db.execute("""
                SELECT labels.name
                FROM labels
                INNER JOIN hosts_labels ON labels.id = hosts_labels.label_id
                WHERE NOT labels.platform AND hosts_labels.host_id = %s
                ORDER BY labels.name
                """, (self.id,))
        return [row[0] for row in rows]


class HostQueueEntry(DBObject):
    def __init__(self, id=None, row=None):
        assert id or row
        super(HostQueueEntry, self).__init__(id=id, row=row)
        self.job = Job(self.job_id)

        if self.host_id:
            self.host = Host(self.host_id)
        else:
            self.host = None

        self.queue_log_path = os.path.join(self.job.results_dir(),
                                           'queue.log.' + str(self.id))


    @classmethod
    def _get_table(cls):
        return 'host_queue_entries'


    @classmethod
    def _fields(cls):
        return ['id', 'job_id', 'host_id', 'priority', 'status',
                  'meta_host', 'active', 'complete', 'deleted']


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
        queue_log = open(self.queue_log_path, 'a', 0)
        queue_log.write(now + ' ' + log_line + '\n')
        queue_log.close()


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


    def results_dir(self):
        if self.job.is_synchronous() or self.job.num_machines() == 1:
            return self.job.job_dir
        else:
            assert self.host
            return os.path.join(self.job.job_dir,
                                self.host.hostname)


    def verify_results_dir(self):
        if self.job.is_synchronous() or self.job.num_machines() > 1:
            assert self.host
            return os.path.join(self.job.job_dir,
                                self.host.hostname)
        else:
            return self.job.job_dir


    def set_status(self, status):
        abort_statuses = ['Abort', 'Aborting', 'Aborted']
        if status not in abort_statuses:
            condition = ' AND '.join(['status <> "%s"' % x
                                      for x in abort_statuses])
        else:
            condition = ''
        self.update_field('status', status, condition=condition)

        if self.host:
            hostname = self.host.hostname
        else:
            hostname = 'no host'
        print "%s/%d status -> %s" % (hostname, self.id, self.status)

        if status in ['Queued']:
            self.update_field('complete', False)
            self.update_field('active', False)

        if status in ['Pending', 'Running', 'Verifying', 'Starting',
                      'Abort', 'Aborting']:
            self.update_field('complete', False)
            self.update_field('active', True)

        if status in ['Failed', 'Completed', 'Stopped', 'Aborted', 'Parsing']:
            self.update_field('complete', True)
            self.update_field('active', False)
            self._email_on_job_complete()


    def _email_on_job_complete(self):
        url = "%s#tab_id=view_job&object_id=%s" % (_base_url, self.job.id)

        if self.job.is_finished():
            subject = "Autotest: Job ID: %s \"%s\" Completed" % (
                self.job.id, self.job.name)
            body = "Job ID: %s\nJob Name: %s\n%s\n" % (
                self.job.id, self.job.name, url)
            send_email(_email_from, self.job.email_list, subject, body)


    def run(self,assigned_host=None):
        if self.meta_host:
            assert assigned_host
            # ensure results dir exists for the queue log
            self.job.create_results_dir()
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
        if self.job.is_synchronous():
            self.job.stop_all_entries()


    def clear_results_dir(self, results_dir=None, dont_delete_files=False):
        results_dir = results_dir or self.results_dir()
        if not os.path.exists(results_dir):
            return
        if dont_delete_files:
            temp_dir = tempfile.mkdtemp(suffix='.clear_results')
            print 'Moving results from %s to %s' % (results_dir,
                                                    temp_dir)
        for filename in os.listdir(results_dir):
            path = os.path.join(results_dir, filename)
            if dont_delete_files:
                shutil.move(path,
                            os.path.join(temp_dir, filename))
            else:
                remove_file_or_dir(path)


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
        return None


    def abort(self, agents_to_abort=[]):
        abort_task = AbortTask(self, agents_to_abort)
        tasks = [abort_task]

        host = self.get_host()
        if host:
            reboot_task = RebootTask(host=host)
            verify_task = VerifyTask(host=host)
            # just to make sure this host does not get taken away
            host.set_status('Rebooting')
            tasks += [reboot_task, verify_task]

        self.set_status('Aborting')
        return Agent(tasks=tasks, queue_entry_ids=[self.id])


class Job(DBObject):
    def __init__(self, id=None, row=None):
        assert id or row
        super(Job, self).__init__(id=id, row=row)

        self.job_dir = os.path.join(RESULTS_DIR, "%s-%s" % (self.id,
                                                            self.owner))


    @classmethod
    def _get_table(cls):
        return 'jobs'


    @classmethod
    def _fields(cls):
        return  ['id', 'owner', 'name', 'priority', 'control_file',
                 'control_type', 'created_on', 'synch_type',
                 'synch_count', 'synchronizing', 'timeout',
                 'run_verify', 'email_list', 'reboot_before', 'reboot_after']


    def is_server_job(self):
        return self.control_type != 2


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


    def is_synchronous(self):
        return self.synch_type == 2


    def is_ready(self):
        if not self.is_synchronous():
            return True
        sql = "job_id=%s AND status='Pending'" % self.id
        count = self.count(sql, table='host_queue_entries')
        return (count == self.num_machines())


    def results_dir(self):
        return self.job_dir

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
        left = self.num_queued()
        print "%s: %s machines left" % (self.name, left)
        return left==0


    def stop_all_entries(self):
        for child_entry in self.get_host_queue_entries():
            if not child_entry.complete:
                child_entry.set_status('Stopped')


    def write_to_machines_file(self, queue_entry):
        hostname = queue_entry.get_host().hostname
        print "writing %s to job %s machines file" % (hostname, self.id)
        file_path = os.path.join(self.job_dir, '.machines')
        mf = open(file_path, 'a')
        mf.write("%s\n" % queue_entry.get_host().hostname)
        mf.close()


    def create_results_dir(self, queue_entry=None):
        print "create: active: %s complete %s" % (self.num_active(),
                                                  self.num_complete())

        if not os.path.exists(self.job_dir):
            os.makedirs(self.job_dir)

        if queue_entry:
            results_dir = queue_entry.results_dir()
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
            return results_dir
        return self.job_dir


    def _write_control_file(self):
        'Writes control file out to disk, returns a filename'
        control_fd, control_filename = tempfile.mkstemp(suffix='.control_file')
        control_file = os.fdopen(control_fd, 'w')
        if self.control_file:
            control_file.write(self.control_file)
        control_file.close()
        return control_filename


    def _get_job_tag(self, queue_entries):
        base_job_tag = "%s-%s" % (self.id, self.owner)
        if self.is_synchronous() or self.num_machines() == 1:
            return base_job_tag
        else:
            return base_job_tag + '/' + queue_entries[0].get_host().hostname


    def _get_autoserv_params(self, queue_entries):
        results_dir = self.create_results_dir(queue_entries[0])
        control_filename = self._write_control_file()
        hostnames = ','.join([entry.get_host().hostname
                              for entry in queue_entries])
        job_tag = self._get_job_tag(queue_entries)

        params = [_autoserv_path, '-P', job_tag, '-p', '-n',
                  '-r', os.path.abspath(results_dir), '-u', self.owner,
                  '-l', self.name, '-m', hostnames, control_filename]

        if not self.is_server_job():
            params.append('-c')

        return params


    def _get_pre_job_tasks(self, queue_entry, verify_task_class=VerifyTask):
        do_reboot = False
        if self.reboot_before == models.RebootBefore.ALWAYS:
            do_reboot = True
        elif self.reboot_before == models.RebootBefore.IF_DIRTY:
            do_reboot = queue_entry.get_host().dirty

        tasks = []
        if do_reboot:
            tasks.append(RebootTask(queue_entry=queue_entry))
        tasks.append(verify_task_class(queue_entry=queue_entry))
        return tasks


    def _run_synchronous(self, queue_entry):
        if not self.is_ready():
            if self.run_verify:
                return Agent(self._get_pre_job_tasks(queue_entry,
                                                     VerifySynchronousTask),
                             [queue_entry.id])
            else:
                return queue_entry.on_pending()

        return self._finish_run(self.get_host_queue_entries())


    def _run_asynchronous(self, queue_entry):
        initial_tasks = []
        if self.run_verify:
            initial_tasks = self._get_pre_job_tasks(queue_entry)
        return self._finish_run([queue_entry], initial_tasks)


    def _finish_run(self, queue_entries, initial_tasks=[]):
        for queue_entry in queue_entries:
            queue_entry.set_status('Starting')
        params = self._get_autoserv_params(queue_entries)
        queue_task = QueueTask(job=self, queue_entries=queue_entries,
                               cmd=params)
        tasks = initial_tasks + [queue_task]
        entry_ids = [entry.id for entry in queue_entries]

        return Agent(tasks, entry_ids, num_processes=len(queue_entries))


    def run(self, queue_entry):
        if self.is_synchronous():
            return self._run_synchronous(queue_entry)
        return self._run_asynchronous(queue_entry)


if __name__ == '__main__':
    main()
