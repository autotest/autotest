__author__ = """Copyright Andy Whitcroft, Martin J. Bligh - 2006, 2007"""

import sys, os, subprocess, time, signal, cPickle, logging

from autotest_lib.client.common_lib import error, utils


# entry points that use subcommand must set this to their logging manager
# to get log redirection for subcommands
logging_manager_object = None


def parallel(tasklist, timeout=None, return_results=False):
    """
    Run a set of predefined subcommands in parallel.

    @param tasklist: A list of subcommand instances to execute.
    @param timeout: Number of seconds after which the commands should timeout.
    @param return_results: If True instead of an AutoServError being raised
            on any error a list of the results|exceptions from the tasks is
            returned.  [default: False]
    """
    run_error = False
    for task in tasklist:
        task.fork_start()

    remaining_timeout = None
    if timeout:
        endtime = time.time() + timeout

    results = []
    for task in tasklist:
        if timeout:
            remaining_timeout = max(endtime - time.time(), 1)
        try:
            status = task.fork_waitfor(timeout=remaining_timeout)
        except error.AutoservSubcommandError:
            run_error = True
        else:
            if status != 0:
                run_error = True

        results.append(cPickle.load(task.result_pickle))
        task.result_pickle.close()

    if return_results:
        return results
    elif run_error:
        message = 'One or more subcommands failed:\n'
        for task, result in zip(tasklist, results):
            message += 'task: %s returned/raised: %r\n' % (task, result)
        raise error.AutoservError(message)


def parallel_simple(function, arglist, log=True, timeout=None,
                    return_results=False):
    """
    Each element in the arglist used to create a subcommand object,
    where that arg is used both as a subdir name, and a single argument
    to pass to "function".

    We create a subcommand object for each element in the list,
    then execute those subcommand objects in parallel.

    NOTE: As an optimization, if len(arglist) == 1 a subcommand is not used.

    @param function: A callable to run in parallel once per arg in arglist.
    @param arglist: A list of single arguments to be used one per subcommand;
            typically a list of machine names.
    @param log: If True, output will be written to output in a subdirectory
            named after each subcommand's arg.
    @param timeout: Number of seconds after which the commands should timeout.
    @param return_results: If True instead of an AutoServError being raised
            on any error a list of the results|exceptions from the function
            called on each arg is returned.  [default: False]

    @returns None or a list of results/exceptions.
    """
    if not arglist:
        logging.warn('parallel_simple was called with an empty arglist, '
                     'did you forget to pass in a list of machines?')
    # Bypass the multithreading if only one machine.
    if len(arglist) == 1:
        arg = arglist[0]
        if return_results:
            try:
                result = function(arg)
            except Exception, e:
                return [e]
            return [result]
        else:
            function(arg)
            return

    subcommands = []
    for arg in arglist:
        args = [arg]
        if log:
            subdir = str(arg)
        else:
            subdir = None
        subcommands.append(subcommand(function, args, subdir))
    return parallel(subcommands, timeout, return_results=return_results)


class subcommand(object):
    fork_hooks, join_hooks = [], []

    def __init__(self, func, args, subdir = None):
        # func(args) - the subcommand to run
        # subdir     - the subdirectory to log results in
        if subdir:
            self.subdir = os.path.abspath(subdir)
            if not os.path.exists(self.subdir):
                os.mkdir(self.subdir)
            self.debug = os.path.join(self.subdir, 'debug')
            if not os.path.exists(self.debug):
                os.mkdir(self.debug)
        else:
            self.subdir = None
            self.debug = None

        self.func = func
        self.args = args
        self.lambda_function = lambda: func(*args)
        self.pid = None
        self.returncode = None


    def __str__(self):
        return str('subcommand(func=%s,  args=%s, subdir=%s)' %
                   (self.func, self.args, self.subdir))


    @classmethod
    def register_fork_hook(cls, hook):
        """ Register a function to be called from the child process after
        forking. """
        cls.fork_hooks.append(hook)


    @classmethod
    def register_join_hook(cls, hook):
        """ Register a function to be called when from the child process
        just before the child process terminates (joins to the parent). """
        cls.join_hooks.append(hook)


    def redirect_output(self):
        if self.subdir and logging_manager_object:
            tag = os.path.basename(self.subdir)
            logging_manager_object.tee_redirect_debug_dir(self.debug, tag=tag)


    def fork_start(self):
        sys.stdout.flush()
        sys.stderr.flush()
        r, w = os.pipe()
        self.returncode = None
        self.pid = os.fork()

        if self.pid:                            # I am the parent
            os.close(w)
            self.result_pickle = os.fdopen(r, 'r')
            return
        else:
            os.close(r)

        # We are the child from this point on. Never return.
        signal.signal(signal.SIGTERM, signal.SIG_DFL) # clear handler
        if self.subdir:
            os.chdir(self.subdir)
        self.redirect_output()

        try:
            for hook in self.fork_hooks:
                hook(self)
            result = self.lambda_function()
            os.write(w, cPickle.dumps(result, cPickle.HIGHEST_PROTOCOL))
            exit_code = 0
        except Exception, e:
            logging.exception('function failed')
            exit_code = 1
            os.write(w, cPickle.dumps(e, cPickle.HIGHEST_PROTOCOL))

        os.close(w)

        try:
            for hook in self.join_hooks:
                hook(self)
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(exit_code)


    def _handle_exitstatus(self, sts):
        """
        This is partially borrowed from subprocess.Popen.
        """
        if os.WIFSIGNALED(sts):
            self.returncode = -os.WTERMSIG(sts)
        elif os.WIFEXITED(sts):
            self.returncode = os.WEXITSTATUS(sts)
        else:
            # Should never happen
            raise RuntimeError("Unknown child exit status!")

        if self.returncode != 0:
            print "subcommand failed pid %d" % self.pid
            print "%s" % (self.func,)
            print "rc=%d" % self.returncode
            print
            if self.debug:
                stderr_file = os.path.join(self.debug, 'autoserv.stderr')
                if os.path.exists(stderr_file):
                    for line in open(stderr_file).readlines():
                        print line,
            print "\n--------------------------------------------\n"
            raise error.AutoservSubcommandError(self.func, self.returncode)


    def poll(self):
        """
        This is borrowed from subprocess.Popen.
        """
        if self.returncode is None:
            try:
                pid, sts = os.waitpid(self.pid, os.WNOHANG)
                if pid == self.pid:
                    self._handle_exitstatus(sts)
            except os.error:
                pass
        return self.returncode


    def wait(self):
        """
        This is borrowed from subprocess.Popen.
        """
        if self.returncode is None:
            pid, sts = os.waitpid(self.pid, 0)
            self._handle_exitstatus(sts)
        return self.returncode


    def fork_waitfor(self, timeout=None):
        if not timeout:
            return self.wait()
        else:
            end_time = time.time() + timeout
            while time.time() <= end_time:
                returncode = self.poll()
                if returncode is not None:
                    return returncode
                time.sleep(1)

            utils.nuke_pid(self.pid)
            print "subcommand failed pid %d" % self.pid
            print "%s" % (self.func,)
            print "timeout after %ds" % timeout
            print
            return None
