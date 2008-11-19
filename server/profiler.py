import itertools
from autotest_lib.server import autotest



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


class profiler_proxy(object):
    """ This is a server-side class that acts as a proxy to a real client-side
    profiler class."""

    def __init__(self, job, profiler_name):
        self.job = job
        self.name = profiler_name
        self.installed_hosts = {}


    def _install(self):
        """ Install autotest on any current job hosts. """
        current_job_hosts = self.job.hosts
        current_profiler_hosts = set(self.installed_hosts.keys())
        # install autotest on any new hosts in job.hosts
        for host in current_job_hosts - current_profiler_hosts:
            tmp_dir = host.get_tmp_dir(parent="/tmp/profilers")
            at = autotest.Autotest(host)
            at.install(autodir=tmp_dir)
            self.installed_hosts[host] = at
        # drop any installs from hosts no longer in job.hosts
        for host in current_profiler_hosts - current_job_hosts:
            del self.installed_hosts[host]


    def setup(self, *args, **dargs):
        validate_args(args)
        validate_args(dargs)
        self._install()


    def initialize(self, *args, **dargs):
        validate_args(args)
        validate_args(dargs)


    def start(self, test):
        pass


    def stop(self, test):
        pass


    def report(self, test):
        pass
