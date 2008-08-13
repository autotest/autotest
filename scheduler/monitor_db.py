#!/usr/bin/python -u

"""
Autotest scheduler
"""


import os, sys, tempfile, shutil, MySQLdb, time, traceback, subprocess, Queue
import optparse, signal, smtplib, socket, datetime, stat, pwd, errno
import common
from autotest_lib.client.common_lib import global_config, host_protections


RESULTS_DIR = '.'
AUTOSERV_NICE_LEVEL = 10

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

    os.environ['PATH'] = AUTOTEST_SERVER_DIR + ':' + os.environ['PATH']
    global _db
    _db = DatabaseConn()
    _db.connect()

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


class DatabaseConn:
    def __init__(self):
        self.reconnect_wait = 20
        self.conn = None
        self.cur = None

        import MySQLdb.converters
        self.convert_dict = MySQLdb.converters.conversions
        self.convert_dict.setdefault(bool, self.convert_boolean)


    @staticmethod
    def convert_boolean(boolean, conversion_dict):
        'Convert booleans to integer strings'
        return str(int(boolean))


    def connect(self, db_name=None):
        self.disconnect()

        # get global config and parse for info
        c = global_config.global_config
        dbase = "AUTOTEST_WEB"
        db_host = c.get_config_value(dbase, "host")
        if db_name is None:
            db_name = c.get_config_value(dbase, "database")

        if _testing_mode:
            db_name = 'stresstest_autotest_web'

        db_user = c.get_config_value(dbase, "user")
        db_pass = c.get_config_value(dbase, "password")

        while not self.conn:
            try:
                self.conn = MySQLdb.connect(
                    host=db_host, user=db_user, passwd=db_pass,
                    db=db_name, conv=self.convert_dict)

                self.conn.autocommit(True)
                self.cur = self.conn.cursor()
            except MySQLdb.OperationalError:
                traceback.print_exc()
                print "Can't connect to MYSQL; reconnecting"
                time.sleep(self.reconnect_wait)
                self.disconnect()


    def disconnect(self):
        if self.conn:
            self.conn.close()
        self.conn = None
        self.cur = None


    def execute(self, *args, **dargs):
        while (True):
            try:
                self.cur.execute(*args, **dargs)
                return self.cur.fetchall()
            except MySQLdb.OperationalError:
                traceback.print_exc()
                print "MYSQL connection died; reconnecting"
                time.sleep(self.reconnect_wait)
                self.connect()


def generate_parse_command(results_dir, flags=""):
    parse = os.path.abspath(os.path.join(AUTOTEST_TKO_DIR, 'parse'))
    output = os.path.abspath(os.path.join(results_dir, '.parse.log'))
    cmd = "%s %s -r -o %s > %s 2>&1 &"
    return cmd % (parse, flags, results_dir, output)


def parse_results(results_dir, flags=""):
    if _testing_mode:
        return
    os.system(generate_parse_command(results_dir, flags))




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
        # see os.getlogin() online docs
        self._sender = pwd.getpwuid(os.getuid())[0]


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
        msg = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (
            self._sender, _notify_email, subject, body)

        mailer = smtplib.SMTP('localhost')
        mailer.sendmail(self._sender, _notify_email, msg)
        mailer.quit()
        self._emails = []

email_manager = EmailNotificationManager()


class Dispatcher:
    autoserv_procs_cache = None
    max_running_agents = global_config.global_config.get_config_value(
        _global_config_section, 'max_running_jobs', type=int)
    max_jobs_started_per_cycle = (
        global_config.global_config.get_config_value(
            _global_config_section, 'max_jobs_started_per_cycle', type=int))
    clean_interval = (
        global_config.global_config.get_config_value(
            _global_config_section, 'clean_interval_minutes', type=int))

    def __init__(self):
        self._agents = []
        self._last_clean_time = time.time()


    def do_initial_recovery(self, recover_hosts=True):
        # always recover processes
        self._recover_processes()

        if recover_hosts:
            self._recover_hosts()


    def tick(self):
        Dispatcher.autoserv_procs_cache = None
        if self._last_clean_time + self.clean_interval * 60 < time.time():
            self._abort_timed_out_jobs()
            self._clear_inactive_blocks()
            self._last_clean_time = time.time()
        self._find_aborting()
        self._schedule_new_jobs()
        self._handle_agents()
        email_manager.send_queued_emails()


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


    def num_started_agents(self):
        return len([agent for agent in self._agents
                    if agent.is_started()])


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
            pid, exit_code = run_monitor.get_pidfile_info()
            if pid is None:
                # autoserv apparently never got run, so requeue
                requeue_entries.append(queue_entry)
                continue
            if queue_entry.id in recovered_entry_ids:
                # synchronous job we've already recovered
                continue
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
            queue_host = queue_entry.get_host()
            reboot_task = RebootTask(queue_host)
            verify_task = VerifyTask(host = queue_host)
            self.add_agent(Agent(tasks=[reboot_task,
                                        verify_task],
                           queue_entry_ids=[queue_entry.id]))
            queue_entry.set_status('Aborted')
            # Secure the host from being picked up
            queue_host.set_status('Rebooting')
            rebooting_host_ids.add(queue_host.id)

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


    def _recover_hosts(self):
        # recover "Repair Failed" hosts
        message = 'Reverifying dead host %s'
        self._reverify_hosts_where("status = 'Repair Failed'",
                                   print_message=message)


    def _abort_timed_out_jobs(self):
        """
        Aborts all jobs that have timed out and not completed
        """
        update = """
            UPDATE host_queue_entries INNER JOIN jobs
                ON host_queue_entries.job_id = jobs.id"""
        timed_out = ' AND jobs.created_on + INTERVAL jobs.timeout HOUR < NOW()'

        _db.execute(update + """
            SET host_queue_entries.status = 'Abort'
            WHERE host_queue_entries.active IS TRUE""" + timed_out)

        _db.execute(update + """
            SET host_queue_entries.status = 'Aborted',
                host_queue_entries.active = FALSE,
                host_queue_entries.complete = TRUE
            WHERE host_queue_entries.active IS FALSE
                AND host_queue_entries.complete IS FALSE""" + timed_out)


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


    def _extract_host_and_queue_entry(self, row):
        # each row contains host columns followed by host queue entry
        # columns
        num_host_cols = Host.num_cols()
        assert len(row) == num_host_cols + HostQueueEntry.num_cols()
        host = Host(row=row[:num_host_cols])
        queue_entry = HostQueueEntry(row=row[num_host_cols:])
        return host, queue_entry


    def _get_runnable_entries(self, extra_join='', extra_where=''):
        query = (
            'SELECT DISTINCT h.*, queued_hqe.* FROM hosts h '
            # join with running entries
            """
            LEFT JOIN host_queue_entries AS active_hqe
            ON (h.id = active_hqe.host_id AND active_hqe.active)
            """ +
            extra_join +
            # exclude hosts with a running entry
            'WHERE active_hqe.host_id IS NULL '
            # exclude locked and non-Ready hosts
            """
            AND h.locked=false
            AND (h.status IS null OR h.status='Ready')
            """)
        if extra_where:
            query += 'AND ' + extra_where + '\n'
        # respect priority, then sort by ID (most recent first)
        query += 'ORDER BY queued_hqe.priority DESC, queued_hqe.id'

        rows = _db.execute(query)
        return [self._extract_host_and_queue_entry(row) for row in rows]


    def _get_runnable_nonmetahosts(self):
        # find queued HQEs scheduled directly against hosts
        queued_hqe_join = """
        INNER JOIN host_queue_entries AS queued_hqe
        ON (h.id = queued_hqe.host_id
            AND NOT queued_hqe.active AND NOT queued_hqe.complete)
        """
        return self._get_runnable_entries(queued_hqe_join)


    def _get_runnable_metahosts(self):
        # join with labels for metahost matching
        labels_join = 'INNER JOIN hosts_labels hl ON (hl.host_id=h.id)'
        # find queued HQEs scheduled for metahosts that match idle hosts
        queued_hqe_join = """
        INNER JOIN host_queue_entries AS queued_hqe
        ON (queued_hqe.meta_host = hl.label_id
            AND queued_hqe.host_id IS NULL
            AND NOT queued_hqe.active AND NOT queued_hqe.complete)
        """
        # need to exclude acl-inaccessible hosts
        acl_join = """
        INNER JOIN acl_groups_hosts ON h.id=acl_groups_hosts.host_id
        INNER JOIN acl_groups_users
          ON acl_groups_users.acl_group_id=acl_groups_hosts.acl_group_id
        INNER JOIN users ON acl_groups_users.user_id=users.id
        INNER JOIN jobs
          ON users.login=jobs.owner AND jobs.id=queued_hqe.job_id
        """
        # need to exclude blocked hosts
        block_join = """
        LEFT JOIN ineligible_host_queues AS ihq
        ON (ihq.job_id=queued_hqe.job_id AND ihq.host_id=h.id)
        """
        block_where = 'ihq.id IS NULL AND h.invalid = FALSE'
        extra_join = '\n'.join([labels_join, queued_hqe_join,
                                acl_join, block_join])
        return self._get_runnable_entries(extra_join,
                                          extra_where=block_where)


    def _schedule_new_jobs(self):
        print "finding work"

        scheduled_hosts, scheduled_queue_entries = set(), set()
        runnable = (self._get_runnable_nonmetahosts() +
                    self._get_runnable_metahosts())
        for host, queue_entry in runnable:
            # we may get duplicate entries for a host or a queue
            # entry.  we need to schedule each host and each queue
            # entry only once.
            if (host.id in scheduled_hosts or
                queue_entry.id in scheduled_queue_entries):
                continue
            agent = queue_entry.run(assigned_host=host)
            self.add_agent(agent)
            scheduled_hosts.add(host.id)
            scheduled_queue_entries.add(queue_entry.id)


    def _find_aborting(self):
        num_aborted = 0
        # Find jobs that are aborting
        for entry in queue_entries_to_abort():
            agents_to_abort = self.get_agents(entry)
            entry_host = entry.get_host()
            reboot_task = RebootTask(entry_host)
            verify_task = VerifyTask(host = entry_host)
            tasks = [reboot_task, verify_task]
            if agents_to_abort:
                abort_task = AbortTask(entry, agents_to_abort)
                for agent in agents_to_abort:
                    self.remove_agent(agent)
                tasks.insert(0, abort_task)
            else:
                entry.set_status('Aborted')
                # just to make sure this host does not get
                # taken away
                entry_host.set_status('Rebooting')
            self.add_agent(Agent(tasks=tasks,
                                 queue_entry_ids = [entry.id]))
            num_aborted += 1
            if num_aborted >= 50:
                break


    def _handle_agents(self):
        still_running = []
        num_started = self.num_started_agents()
        start_new = (num_started < self.max_running_agents)
        num_started_this_cycle = 0
        for agent in self._agents:
            if not agent.is_started():
                if not start_new:
                    still_running.append(agent)
                    continue
                num_started += 1
                num_started_this_cycle += 1
                if (num_started >= self.max_running_agents or
                    num_started_this_cycle >=
                    self.max_jobs_started_per_cycle):
                    start_new = False
            agent.tick()
            if not agent.is_done():
                still_running.append(agent)
            else:
                print "agent finished"
        self._agents = still_running
        print num_started, 'running agents'


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
    def __init__(self, results_dir, cmd=None, nice_level=None,
                 log_file=None):
        self.results_dir = os.path.abspath(results_dir)
        self.pid_file = os.path.join(results_dir, AUTOSERV_PID_FILE)
        self.lost_process = False
        self.start_time = time.time()
        super(PidfileRunMonitor, self).__init__(cmd, nice_level, log_file)


    def get_pid(self):
        pid, exit_status = self.get_pidfile_info()
        assert pid is not None
        return pid


    def _check_command_line(self, command_line, spacer=' ',
                            print_error=False):
        results_dir_arg = spacer.join(('', '-r', self.results_dir, ''))
        match = results_dir_arg in command_line
        if print_error and not match:
            print '%s not found in %s' % (repr(results_dir_arg),
                                          repr(command_line))
        return match


    def _check_proc_fs(self, pid):
        cmdline_path = os.path.join('/proc', str(pid), 'cmdline')
        try:
            cmdline_file = open(cmdline_path, 'r')
            cmdline = cmdline_file.read().strip()
            cmdline_file.close()
        except IOError:
            return False
        # /proc/.../cmdline has \x00 separating args
        return self._check_command_line(cmdline, spacer='\x00',
                                        print_error=True)


    def read_pidfile(self):
        if not os.path.exists(self.pid_file):
            return None, None
        file_obj = open(self.pid_file, 'r')
        lines = file_obj.readlines()
        file_obj.close()
        assert 1 <= len(lines) <= 2
        try:
            pid = int(lines[0])
            exit_status = None
            if len(lines) == 2:
                exit_status = int(lines[1])
        except ValueError, exc:
            raise PidfileException('Corrupt pid file: ' +
                                   str(exc.args))

        return pid, exit_status


    def _find_autoserv_proc(self):
        autoserv_procs = Dispatcher.find_autoservs()
        for pid, args in autoserv_procs.iteritems():
            if self._check_command_line(args):
                return pid, args
        return None, None


    def get_pidfile_info(self):
        """\
        Returns:
         None, None if autoserv has not yet run
         pid,  None if autoserv is running
         pid, exit_status if autoserv has completed
        """
        if self.lost_process:
            return self.pid, self.exit_status

        pid, exit_status = self.read_pidfile()

        if pid is None:
            return self._handle_no_pid()

        if exit_status is None:
            # double check whether or not autoserv is running
            proc_running = self._check_proc_fs(pid)
            if proc_running:
                return pid, exit_status

            # pid but no process - maybe process *just* exited
            pid, exit_status = self.read_pidfile()
            if exit_status is None:
                # autoserv exited without writing an exit code
                # to the pidfile
                error = ('autoserv died without writing exit '
                         'code')
                message = error + '\nPid: %s\nPidfile: %s' % (
                    pid, self.pid_file)
                print message
                email_manager.enqueue_notify_email(error,
                                                   message)
                self.on_lost_process(pid)
                return self.pid, self.exit_status

        return pid, exit_status


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
            return self.pid, self.exit_status

        return None, None


    def on_lost_process(self, pid):
        """\
        Called when autoserv has exited without writing an exit status,
        or we've timed out waiting for autoserv to write a pid to the
        pidfile.  In either case, we just return failure and the caller
        should signal some kind of warning.

        pid is unimportant here, as it shouldn't be used by anyone.
        """
        self.lost_process = True
        self.pid = pid
        self.exit_status = 1


    def exit_code(self):
        pid, exit_code = self.get_pidfile_info()
        return exit_code


class Agent(object):
    def __init__(self, tasks, queue_entry_ids=[]):
        self.active_task = None
        self.queue = Queue.Queue(0)
        self.dispatcher = None
        self.queue_entry_ids = queue_entry_ids

        for task in tasks:
            self.add_task(task)


    def add_task(self, task):
        self.queue.put_nowait(task)
        task.agent = self


    def tick(self):
        print "agent tick"
        if self.active_task and not self.active_task.is_done():
            self.active_task.poll()
        else:
            self._next_task();


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


    def is_started(self):
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
            if hasattr(self, 'host'):
                log_file = os.path.join(RESULTS_DIR, 'hosts',
                                        self.host.hostname)
            self.monitor = RunMonitor(
                self.cmd, nice_level = AUTOSERV_NICE_LEVEL,
                log_file = log_file)
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
    def __init__(self, queue_entry=None, host=None, run_verify=True):
        assert bool(queue_entry) != bool(host)

        self.host = host or queue_entry.host
        self.queue_entry = queue_entry

        self.create_temp_resultsdir('.verify')

        # TODO:
        # While it is rediculous to instantiate a verify task object
        # that doesnt actually run the verify task, this is hopefully a
        # temporary hack and will have a cleaner way to skip this
        # step later. (while ensuring that the original semantics don't change)
        if not run_verify:
            cmd = ["true"]
        else:
            cmd = [_autoserv_path,'-v','-m',self.host.hostname,
                   '-r', self.temp_results_dir]

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
            print ('Warning: removing existing destination file ' +
                   dest)
            remove_file_or_dir(dest)
        shutil.move(source, dest)


class VerifySynchronousTask(VerifyTask):
    def __init__(self, queue_entry, run_verify=True):
        super(VerifySynchronousTask, self).__init__(queue_entry=queue_entry,
                                                    run_verify=run_verify)


    def epilog(self):
        super(VerifySynchronousTask, self).epilog()
        if self.success:
            if self.queue_entry.job.num_complete() > 0:
                # some other entry failed verify, and we've
                # already been marked as stopped
                return

            self.queue_entry.set_status('Pending')
            job = self.queue_entry.job
            if job.is_ready():
                agent = job.run(self.queue_entry)
                self.agent.dispatcher.add_agent(agent)

class QueueTask(AgentTask):
    def __init__(self, job, queue_entries, cmd):
        super(QueueTask, self).__init__(cmd)
        self.job = job
        self.queue_entries = queue_entries


    @staticmethod
    def _write_keyval(results_dir, field, value):
        key_path = os.path.join(results_dir, 'keyval')
        keyval_file = open(key_path, 'a')
        print >> keyval_file, '%s=%d' % (field, value)
        keyval_file.close()


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
        self._write_keyval(self.results_dir(), "job_queued", queued)
        self._write_keyval(self.results_dir(), "job_started", started)
        for queue_entry in self.queue_entries:
            print "starting queue_task on %s/%s" % (queue_entry.host.hostname, queue_entry.id)
            queue_entry.set_status('Running')
            queue_entry.host.set_status('Running')
        if (not self.job.is_synchronous() and
            self.job.num_machines() > 1):
            assert len(self.queue_entries) == 1
            self.job.write_to_machines_file(self.queue_entries[0])


    def _finish_task(self):
        # write out the finished time into the results keyval
        finished = time.time()
        self._write_keyval(self.results_dir(), "job_finished",
                           finished)

        # parse the results of the job
        if self.job.is_synchronous() or self.job.num_machines() == 1:
            parse_results(self.job.results_dir())
        else:
            for queue_entry in self.queue_entries:
                parse_results(queue_entry.results_dir(),
                              flags="-l 2")


    def abort(self):
        super(QueueTask, self).abort()
        self._finish_task()


    def epilog(self):
        super(QueueTask, self).epilog()
        if self.success:
            status = 'Completed'
        else:
            status = 'Failed'

        for queue_entry in self.queue_entries:
            queue_entry.set_status(status)
            queue_entry.host.set_status('Ready')

        self._finish_task()

        print "queue_task finished with %s/%s" % (status, self.success)


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
    def __init__(self, host):
        global _autoserv_path

        # Current implementation of autoserv requires control file
        # to be passed on reboot action request. TODO: remove when no
        # longer appropriate.
        self.create_temp_resultsdir('.reboot')
        self.cmd = [_autoserv_path, '-b', '-m', host.hostname,
                    '-r', self.temp_results_dir, '/dev/null']
        self.host = host
        super(RebootTask, self).__init__(self.cmd,
                           failure_tasks=[RepairTask(host)])


    def prolog(self):
        print "starting reboot task for host: %s" % self.host.hostname
        self.host.set_status("Rebooting")


class AbortTask(AgentTask):
    def __init__(self, queue_entry, agents_to_abort):
        self.queue_entry = queue_entry
        self.agents_to_abort = agents_to_abort
        super(AbortTask, self).__init__('')


    def prolog(self):
        print "starting abort on host %s, job %s" % (
                self.queue_entry.host_id, self.queue_entry.job_id)
        self.queue_entry.set_status('Aborting')


    def epilog(self):
        super(AbortTask, self).epilog()
        self.queue_entry.set_status('Aborted')
        self.success = True


    def run(self):
        for agent in self.agents_to_abort:
            if (agent.active_task):
                agent.active_task.abort()


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


    @classmethod
    def fetch(cls, where, params=()):
        rows = _db.execute(
            'SELECT * FROM %s WHERE %s' % (cls._get_table(), where),
            params)
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


class Host(DBObject):
    def __init__(self, id=None, row=None):
        super(Host, self).__init__(id=id, row=row)


    @classmethod
    def _get_table(cls):
        return 'hosts'


    @classmethod
    def _fields(cls):
        return ['id', 'hostname', 'locked', 'synch_id','status',
                'invalid', 'protection', 'locked_by_id', 'lock_time']


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

        if status in ['Failed', 'Completed', 'Stopped', 'Aborted']:
            self.update_field('complete', True)
            self.update_field('active', False)


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
                 'synch_count', 'synchronizing', 'timeout', 'run_verify']


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
        return (count == self.synch_count)


    def ready_to_synchronize(self):
        # heuristic
        queue_entries = self.get_host_queue_entries()
        count = 0
        for queue_entry in queue_entries:
            if queue_entry.status == 'Pending':
                count += 1

        return (count/self.synch_count >= 0.5)


    def start_synchronizing(self):
        self.update_field('synchronizing', True)


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

    def stop_synchronizing(self):
        self.update_field('synchronizing', False)
        self.set_status('Queued', update_queues = False)


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
            return queue_entry.results_dir()
        return self.job_dir


    def run(self, queue_entry):
        results_dir = self.create_results_dir(queue_entry)

        queue_entry.set_status('Starting')

        if self.is_synchronous():
            if not self.is_ready():
                return Agent([VerifySynchronousTask(
                                queue_entry=queue_entry,
                                run_verify=self.run_verify)],
                             [queue_entry.id])

        ctrl = open(os.tmpnam(), 'w')
        if self.control_file:
            ctrl.write(self.control_file)
        else:
            ctrl.write("")
        ctrl.flush()

        if self.is_synchronous():
            queue_entries = self.get_host_queue_entries()
        else:
            assert queue_entry
            queue_entries = [queue_entry]
        hostnames = ','.join([entry.get_host().hostname
                              for entry in queue_entries])

        # determine the job tag
        if self.is_synchronous() or self.num_machines() == 1:
            job_name = "%s-%s" % (self.id, self.owner)
        else:
            job_name = "%s-%s/%s" % (self.id, self.owner,
                                     hostnames)

        params = [_autoserv_path, '-P', job_name, '-p', '-n',
                  '-r', os.path.abspath(results_dir),
                  '-b', '-u', self.owner, '-l', self.name,
                  '-m', hostnames, ctrl.name]

        if not self.is_server_job():
            params.append('-c')

        tasks = []
        if not self.is_synchronous():
            tasks.append(VerifyTask(queue_entry, run_verify=self.run_verify))

        tasks.append(QueueTask(job=self,
                               queue_entries=queue_entries,
                               cmd=params))

        ids = []
        for entry in queue_entries:
            ids.append(entry.id)

        agent = Agent(tasks, ids)

        return agent


if __name__ == '__main__':
    main()
