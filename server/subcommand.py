__author__ = """Copyright Andy Whitcroft, Martin J. Bligh - 2006, 2007"""

import sys, os, subprocess, traceback, time, signal

from autotest_lib.client.common_lib import error, utils


def parallel(tasklist, timeout=None):
    """Run an set of predefined subcommands in parallel"""
    pids = []
    run_error = False
    for task in tasklist:
        task.fork_start()

    remaining_timeout = None
    if timeout:
        endtime = time.time() + timeout

    for task in tasklist:
        if timeout:
            remaining_timeout = max(endtime - time.time(), 1)
        try:
            status = task.fork_waitfor(remaining_timeout)
        except error.AutoservSubcommandError:
            run_error = True
        else:
            if status != 0:
                run_error = True

    if run_error:
        raise error.AutoservError('One or more subcommands failed')


def parallel_simple(function, arglist, log=True, timeout=None):
    """Each element in the arglist used to create a subcommand object,
    where that arg is used both as a subdir name, and a single argument
    to pass to "function".
    We create a subcommand object for each element in the list,
    then execute those subcommand objects in parallel."""

    # Bypass the multithreading if only one machine.
    if len (arglist) == 1:
        function(arglist[0])
        return

    subcommands = []
    for arg in arglist:
        args = [arg]
        if log:
            subdir = str(arg)
        else:
            subdir = None
        subcommands.append(subcommand(function, args, subdir))
    parallel(subcommands, timeout)


def _where_art_thy_filehandles():
    os.system("ls -l /proc/%d/fd >> /dev/tty" % os.getpid())


def _print_to_tty(string):
    open('/dev/tty', 'w').write(string + '\n')


def _redirect_stream(fd, output):
    newfd = os.open(output, os.O_WRONLY | os.O_CREAT)
    os.dup2(newfd, fd)
    os.close(newfd)
    if fd == 1:
        sys.stdout = os.fdopen(fd, 'w')
    if fd == 2:
        sys.stderr = os.fdopen(fd, 'w')


def _redirect_stream_tee(fd, output, tag):
    """Use the low-level fork & pipe operations here to get a fd,
    not a filehandle. This ensures that we get both the
    filehandle and fd for stdout/stderr redirected correctly."""
    r, w = os.pipe()
    pid = os.fork()
    if pid:                                 # Parent
        os.dup2(w, fd)
        os.close(r)
        os.close(w)
        if fd == 1:
            sys.stdout = os.fdopen(fd, 'w', 1)
        if fd == 2:
            sys.stderr = os.fdopen(fd, 'w', 1)
        return
    else:                                   # Child
        signal.signal(signal.SIGTERM, signal.SIG_DFL) # clear handler
        os.close(w)
        log = open(output, 'w')
        f = os.fdopen(r, 'r')
        for line in iter(f.readline, ''):
            # Tee straight to file
            log.write(line)
            log.flush()
            # Prepend stdout with the tag
            print tag + ' : ' + line,
            sys.stdout.flush()
        log.close()
        os._exit(0)


class subcommand:
    def __init__(self, func, args, subdir = None, stdprint = True):
        # func(args) - the subcommand to run
        # subdir     - the subdirectory to log results in
        # stdprint   - whether to print results to stdout/stderr
        if subdir:
            self.subdir = os.path.abspath(subdir)
            if not os.path.exists(self.subdir):
                os.mkdir(self.subdir)
            self.debug = os.path.join(self.subdir, 'debug')
            if not os.path.exists(self.debug):
                os.mkdir(self.debug)
            self.stdout = os.path.join(self.debug, 'stdout')
            self.stderr = os.path.join(self.debug, 'stderr')
        else:
            self.subdir = None
            self.debug = '/dev/null'
            self.stdout = '/dev/null'
            self.stderr = '/dev/null'

        self.func = func
        self.args = args
        self.lambda_function = lambda: func(*args)
        self.pid = None
        self.stdprint = stdprint


    def redirect_output(self):
        if self.stdprint:
            if self.subdir:
                tag = os.path.basename(self.subdir)
                _redirect_stream_tee(1, self.stdout, tag)
                _redirect_stream_tee(2, self.stderr, tag)
        else:
            _redirect_stream(1, self.stdout)
            _redirect_stream(2, self.stderr)


    def fork_start(self):
        sys.stdout.flush()
        sys.stderr.flush()
        self.pid = os.fork()

        if self.pid:                            # I am the parent
            return

        # We are the child from this point on. Never return.
        signal.signal(signal.SIGTERM, signal.SIG_DFL) # clear handler
        if self.subdir:
            os.chdir(self.subdir)
        self.redirect_output()

        try:
            self.lambda_function()

        except:
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)

        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


    def fork_waitfor(self, timeout=None):
        if not timeout:
            (pid, status) = os.waitpid(self.pid, 0)
        else:
            pid = None
            start_time = time.time()
            while time.time() <= start_time + timeout:
                (pid, status) = os.waitpid(self.pid, os.WNOHANG)
                if pid:
                    break
                time.sleep(1)

            if not pid:
                utils.nuke_pid(self.pid)
                print "subcommand failed pid %d" % self.pid
                print "%s" % (self.func,)
                print "timeout after %ds" % timeout
                print
                return None

        if status != 0:
            print "subcommand failed pid %d" % pid
            print "%s" % (self.func,)
            print "rc=%d" % status
            print
            if os.path.exists(self.stderr):
                for line in open(self.stderr).readlines():
                    print line,
            print "\n--------------------------------------------\n"
            raise error.AutoservSubcommandError(self.func, status)
        return status
