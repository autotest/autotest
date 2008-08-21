import os, sys


class ParallelError(Exception):
    def __init__(self, str, errors):
        self.str = str
        self.errors = errors
        Exception.__init__(self, str)


class ParallelExecute(object):
    def __init__(self, functions, max_simultaneous_procs=20):
        """\
        This takes in a dictionary of functions which map to a set of
        functions that they depend on.

        functions: This is either a list of or dictionary of functions to
                   be run.  If it's a dictionary, the value should be a set
                   of other functions this function is dependent on.  If its
                   a list (or tuple or anything iterable that returns a
                   single element each iteration), then it's assumed that
                   there are no dependencies.

        max_simultaneous_procs: Throttle the number of processes we have
                                running at once.
        """
        if not isinstance(functions, dict):
            function_list = functions
            functions = {}
            for fn in function_list:
                functions[fn] = set()

        dependents = {}
        for fn, deps in functions.iteritems():
            dependents[fn] = []
        for fn, deps in functions.iteritems():
            for dep in deps:
                dependents[dep].append(fn)

        self.max_procs = max_simultaneous_procs
        self.functions = functions
        self.dependents = dependents
        self.pid_map = {}
        self.ready_to_run = []


    def _run(self, function):
        self.functions.pop(function)
        pid = os.fork()
        if pid:
            self.pid_map[pid] = function
        else:
            function()
            sys.exit(0)


    def run_until_completion(self):
        for fn, deps in self.functions.iteritems():
            if len(deps) == 0:
                self.ready_to_run.append(fn)

        errors = []
        while len(self.pid_map) > 0 or len(self.ready_to_run) > 0:
            max_allowed = self.max_procs - len(self.pid_map)
            max_able = len(self.ready_to_run)
            for i in xrange(min(max_allowed, max_able)):
                self._run(self.ready_to_run.pop())

            # Handle one proc that's finished.
            pid, status = os.wait()
            fn = self.pid_map.pop(pid)
            if status != 0:
                errors.append("%s failed" % fn.__name__)
                continue

            for dependent in self.dependents[fn]:
                self.functions[dependent].remove(fn)
                if len(self.functions[dependent]) == 0:
                    self.ready_to_run.append(dependent)

        if len(self.functions) > 0 and len(errors) == 0:
            errors.append("Deadlock detected")

        if len(errors) > 0:
            msg = "Errors occurred during execution:"
            msg = '\n'.join([msg] + errors)
            raise ParallelError(msg, errors)


def redirect_io(log_file='/dev/null'):
    # Always redirect stdin.
    in_fd = os.open('/dev/null', os.O_RDONLY)
    try:
        os.dup2(in_fd, 0)
    finally:
        os.close(in_fd)

    out_fd = os.open(log_file, os.O_WRONLY | os.O_CREAT)
    try:
        os.dup2(out_fd, 2)
        os.dup2(out_fd, 1)
    finally:
        os.close(out_fd)

    sys.stdin = os.fdopen(0, 'r')
    sys.stdout = os.fdopen(1, 'w')
    sys.stderr = os.fdopen(2, 'w')
