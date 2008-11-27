import os, itertools
from autotest_lib.server import autotest


PROFILER_TMPDIR = "/tmp/profilers"


# control file template for running a job that uses profiler 'name'
run_profiler_control = """\
job.profilers.add(%s)
job.run_test("profiler_test")
job.profilers.delete(%r)
"""


def get_unpassable_types(arg):
    """ Given an argument, returns a set of types contained in arg that are
    unpassable. If arg is an atomic type (e.g. int) it either returns an
    empty set (if the type is passable) or a singleton of the type (if the
    type is not passable). """
    if isinstance(arg, (basestring, int, long)):
        return set()
    elif isinstance(arg, (list, tuple, set, frozenset, dict)):
        if isinstance(arg, dict):
            # keys and values must both be passable
            parts = itertools.chain(arg.iterkeys(), arg.itervalues())
        else:
            # for all other containers we just iterate
            parts = iter(arg)
        types = set()
        for part in parts:
            types |= get_unpassable_types(arg)
        return types
    else:
        return set([type(arg)])


def validate_args(args):
    """ Validates arguments. Lists and dictionaries are valid argument types,
    so you can pass *args and **dargs in directly, rather than having to
    iterate over them yourself. """
    unpassable_types = get_unpassable_types(args)
    if unpassable_types:
        msg = "arguments of type '%s' cannot be passed to remote profilers"
        msg %= ", ".join(t.__name__ for t in unpassable_types)
        raise TypeError(msg)


def encode_args(profiler, args, dargs):
    parts = [repr(profiler)]
    parts += [repr(arg) for arg in dargs]
    parts += ["%s=%r" % darg for darg in dargs.iteritems()]
    return ", ".join(parts)


class profiler_proxy(object):
    """ This is a server-side class that acts as a proxy to a real client-side
    profiler class."""

    def __init__(self, job, profiler_name):
        self.job = job
        self.name = profiler_name
        self.installed_hosts = {}


    def _install(self):
        """ Install autotest on any current job hosts. """
        current_job_hosts = set(host for host in self.job.hosts
                                if not host.get_autodir() or
                                host.get_autodir().startswith(PROFILER_TMPDIR))
        current_profiler_hosts = set(self.installed_hosts.keys())
        # install autotest on any new hosts in job.hosts
        for host in current_job_hosts - current_profiler_hosts:
            tmp_dir = host.get_tmp_dir(parent=PROFILER_TMPDIR)
            at = autotest.Autotest(host)
            at.install(autodir=tmp_dir)
            self.installed_hosts[host] = at
        # drop any installs from hosts no longer in job.hosts
        for host in current_profiler_hosts - current_job_hosts:
            del self.installed_hosts[host]


    def initialize(self, *args, **dargs):
        validate_args(args)
        validate_args(dargs)
        self.args, self.dargs = args, dargs


    def setup(self, *args, **dargs):
        assert self.args == args and self.dargs == dargs
        # the actual setup happens lazily at start()


    def _signal_clients(self, command):
        """ Signal to each client that it should execute profilers.command
        by writing a byte into AUTODIR/profilers.command. """
        for host in self.installed_hosts.iterkeys():
            autodir = host.get_autodir()
            path = os.path.join(autodir, "profiler.%s" % command)
            host.run("echo A > %s" % path)


    def start(self, test):
        self._install()
        encoded_args = encode_args(self.name, self.args, self.dargs)
        control_script = run_profiler_control % (encoded_args, self.name)
        for at in self.installed_hosts.itervalues():
            at.run(control_script, background=True)
        self._signal_clients("start")


    def stop(self, test):
        self._signal_clients("stop")


    def report(self, test):
        self._signal_clients("report")
        # pull back all the results
        for host in self.installed_hosts.iterkeys():
            results_dir = os.path.join(host.get_autodir(), "results",
                                       "default", "profiler_test",
                                       "profiling") + "/"
            local_dir = os.path.join(test.profdir, host.hostname)
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
            try:
                host.get_file(results_dir, local_dir)
            except error.AutoservRunError:
                pass # no files to pull back, nothing we can do
