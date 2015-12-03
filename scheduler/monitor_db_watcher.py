"""
Autotest scheduler watcher main library.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from optparse import OptionParser

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.scheduler import watcher_logging_config
from autotest.client import os_dep
from autotest.client.shared import error, utils
from autotest.client.shared import logging_manager
from autotest.client.shared.settings import settings, SettingsError
from autotest.scheduler import scheduler_logging_config
from autotest.scheduler import monitor_db


PAUSE_LENGTH = 60
STALL_TIMEOUT = 2 * 60 * 60

output_dir = settings.get_value('COMMON', 'test_output_dir', default="")

autodir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

try:
    monitor_db_path = os_dep.command('autotest-scheduler')
    results_dir = os.path.join(output_dir, 'results')
except ValueError:
    monitor_db_path = os.path.join(autodir, 'scheduler', 'autotest-scheduler')
    results_dir = os.path.join(autodir, 'results')


def run_banner_output(cmd):
    """Returns ------ CMD ------\nCMD_OUTPUT in a string"""
    banner_output = '%s\n%%s\n\n' % cmd.center(60, '-')
    command_output = ''
    try:
        cmd_out = utils.run(cmd, ignore_status=True, timeout=30)
        command_output = cmd_out.stdout + cmd_out.stderr
    except error.CmdError:
        command_output = 'Timed out'

    return banner_output % command_output


def kill_monitor():
    logging.info("Killing scheduler")
    # try shutdown first
    utils.signal_program(monitor_db.PID_FILE_PREFIX, sig=signal.SIGINT)
    if utils.program_is_alive(monitor_db.PID_FILE_PREFIX):  # was it killed?
        # give it some time to shutdown
        time.sleep(30)
        # kill it
        utils.signal_program(monitor_db.PID_FILE_PREFIX)


def handle_sigterm(signum, frame):
    logging.info('Caught SIGTERM')
    kill_monitor()
    utils.delete_pid_file_if_exists(monitor_db.WATCHER_PID_FILE_PREFIX)
    sys.exit(1)

signal.signal(signal.SIGTERM, handle_sigterm)


SiteMonitorProc = utils.import_site_class(
    __file__, 'autotest.scheduler.site_monitor_db_watcher',
    'SiteMonitorProc', object)


class MonitorProc(SiteMonitorProc):

    def __init__(self, do_recovery=False):
        args = [monitor_db_path]
        if do_recovery:
            args.append("--recover-hosts")
        args.append(results_dir)

        kill_monitor()
        scheduler_config = scheduler_logging_config.SchedulerLoggingConfig
        log_name = scheduler_config.get_log_name()
        os.environ['AUTOTEST_SCHEDULER_LOG_NAME'] = log_name
        scheduler_log_dir = scheduler_config.get_server_log_dir()
        self.log_path = os.path.join(scheduler_log_dir, log_name)

        self.log_size = 0
        self.last_log_change = time.time()

        logging.info("Starting scheduler with log file %s" % self.log_path)
        self.args = args

        # Allow site specific code to run, set environment variables and
        # modify self.args if desired.
        super(MonitorProc, self).__init__()

    def start(self):
        devnull = open(os.devnull, 'w')
        self.proc = subprocess.Popen(self.args, stdout=devnull)

    def is_running(self):
        if self.proc.poll() is not None:
            logging.info("Scheduler died")
            return False

        old_size = self.log_size
        new_size = os.path.getsize(self.log_path)
        if old_size != new_size:
            logging.info("Log was touched")
            self.log_size = new_size
            self.last_log_change = time.time()
        elif self.last_log_change + STALL_TIMEOUT < time.time():
            logging.info("Scheduler stalled")
            self.collect_stalled_info()
            return False

        return True

    def collect_stalled_info(self):
        INFO_TO_COLLECT = ['uptime',
                           'ps auxwww',
                           'iostat -k -x 2 4',
                           ]
        db_cmd = '/usr/bin/mysqladmin --verbose processlist -u%s -p%s'
        try:
            user = settings.get_value("BACKUP", "user")
            password = settings.get_value("BACKUP", "password")
            db_cmd %= (user, password)
            INFO_TO_COLLECT.append(db_cmd)
        except SettingsError:
            pass
        stall_log_path = self.log_path + '.stall_info'
        log = open(stall_log_path, "w")
        for cmd in INFO_TO_COLLECT:
            log.write(run_banner_output(cmd))

        log.close()


def main():
    parser = OptionParser()
    parser.add_option("-r", action="store_true", dest="recover",
                      help=("run recovery mode (implicit after any crash)"))
    parser.add_option("--background", dest="background", action="store_true",
                      default=False, help=("runs the scheduler monitor on "
                                           "background"))
    (options, args) = parser.parse_args()

    recover = (options.recover is True)

    if len(args) != 0:
        parser.print_help()
        sys.exit(1)

    if os.getuid() == 0:
        logging.critical("Running as root, aborting!")
        sys.exit(1)

    if utils.program_is_alive(monitor_db.WATCHER_PID_FILE_PREFIX):
        logging.critical("autotest-monitor-watcher already running, aborting!")
        sys.exit(1)

    utils.write_pid(monitor_db.WATCHER_PID_FILE_PREFIX)

    if options.background:
        logging_manager.configure_logging(
            watcher_logging_config.WatcherLoggingConfig(use_console=False))

        # Double fork - see http://code.activestate.com/recipes/66012/
        try:
            pid = os.fork()
            if (pid > 0):
                sys.exit(0)  # exit from first parent
        except OSError, e:
            sys.stderr.write("fork #1 failed: (%d) %s\n" %
                             (e.errno, e.strerror))
            sys.exit(1)

        # Decouple from parent environment
        os.chdir("/")
        os.umask(0)
        os.setsid()

        # Second fork
        try:
            pid = os.fork()
            if (pid > 0):
                sys.exit(0)  # exit from second parent
        except OSError, e:
            sys.stderr.write("fork #2 failed: (%d) %s\n" %
                             (e.errno, e.strerror))
            sys.exit(1)
    else:
        logging_manager.configure_logging(
            watcher_logging_config.WatcherLoggingConfig())

    while True:
        proc = MonitorProc(do_recovery=recover)
        proc.start()
        time.sleep(PAUSE_LENGTH)
        while proc.is_running():
            logging.info("Tick")
            time.sleep(PAUSE_LENGTH)
        recover = False
