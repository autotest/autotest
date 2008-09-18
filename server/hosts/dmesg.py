import os, sys, subprocess, tempfile, traceback

from autotest_lib.client.common_lib import utils
from autotest_lib.server import utils as server_utils
from autotest_lib.server.hosts import remote, ssh_host


def _log_and_ignore_exceptions(f):
    """ Decorator for automatically logging an exception during a method call
    and then discarding it. """
    def wrapped(self, *args, **dargs):
        try:
            return f(self, *args, **dargs)
        except Exception, e:
            print "DmesgHost.%s failed with exception %s" % (f.__name__, e)
            print "Exception ignored:"
            traceback.print_exc(file=sys.stdout)
    wrapped.__name__ = f.__name__
    wrapped.__doc__ = f.__doc__
    wrapped.__dict__.update(f.__dict__)
    return wrapped


class DmesgHost(remote.RemoteHost):
    def __init__(self, console_log="dmesg.log", *args, **dargs):
        super(DmesgHost, self).__init__(*args, **dargs)

        self.__last_line = None
        self.__logger = None
        self.__console_log = console_log


    # TODO: replace this with something more generic that doesn't require
    # using SSH. Currently it can't just use self.run because it a) needs
    # it to be a background process and b) needs control over the command
    # std* streams.
    def __run_cmd_on_host(self, cmd, stdin, stdout, stderr):
        base_cmd = ssh_host.SSHHost.ssh_base_command()
        full_cmd = "%s %s \"%s\"" % (base_cmd, self.hostname,
                                     server_utils.sh_escape(cmd))

        return subprocess.Popen(full_cmd, stdin=stdin, stdout=stdout,
                                stderr=stderr, shell=True)


    def reboot_followup(self, *args, **dargs):
        super(DmesgHost, self).reboot_followup(*args, **dargs)
        self.__stop_loggers()
        self.__start_loggers()


    def start_loggers(self):
        super(DmesgHost, self).start_loggers()
        self.__start_loggers()


    @_log_and_ignore_exceptions
    def __start_loggers(self):
        # check if /var/log/kern.log is available, and don't bother doing
        # anything if it's not
        if self.run("ls /var/log/kern.log", ignore_status=True).exit_status:
            return

        devnull_r = open(os.devnull, "r")
        devnull_w = open(os.devnull, "w")

        if self.__last_line is not None and os.path.exists(self.__console_log):
            # find the last log line we've processed
            log_file = open(self.__console_log)
            for line in log_file:
                self.__last_line = line.rstrip("\n")
            # determine what line in kern.log to start processing from
            start_line = 1
            if self.__last_line:
                existing_log = self.run("cat /var/log/kern.log",
                                        stdout_tee=devnull_w,
                                        stderr_tee=devnull_w).stdout
                log_lines = existing_log.split("\n")
                for i, line in reversed(list(enumerate(log_lines))):
                    if self.__last_line == line:
                        start_line = i + 2
                        break
            start_line = "+%d" % start_line
        else:
            # we haven't started logging yet; start from the END of the
            # current log, anything in it is pre-test anyway
            self.__last_line = self.run("tail -n -1 /var/log/kern.log",
                                        stdout_tee=devnull_w,
                                        stderr_tee=devnull_w).stdout
            self.__last_line = self.__last_line.rstrip("\n")
            start_line = "-0"

        tail_cmd = "tail -n %s --retry --follow=name /var/log/kern.log"
        self.__tail_logger = self.__run_cmd_on_host(tail_cmd % start_line,
                                                    stdin=devnull_r,
                                                    stdout=subprocess.PIPE,
                                                    stderr=devnull_w)

        r, w = os.pipe()
        script_path = os.path.join(self.monitordir, "console.py")
        cmd = [sys.executable, script_path, self.__console_log, str(w)]

        self.__warning_stream = os.fdopen(r, "r", 0)
        if self.job:
            self.job.warning_loggers.add(self.__warning_stream)

        self.__logger = subprocess.Popen(cmd, stdin=self.__tail_logger.stdout,
                                         stdout=devnull_w, stderr=devnull_w)
        os.close(w)


    def stop_loggers(self):
        super(DmesgHost, self).stop_loggers()
        self.__stop_loggers()


    @_log_and_ignore_exceptions
    def __stop_loggers(self):
        if self.__logger:
            utils.nuke_subprocess(self.__logger)
            utils.nuke_subprocess(self.__tail_logger)
            self.__logger = self.__tail_logger = None
            if self.job:
                self.job.warning_loggers.discard(self.__warning_stream)
            self.__warning_stream.close()
