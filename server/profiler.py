import itertools
import common


def _get_unpassable_types(arg):
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
            types |= _get_unpassable_types(part)
        return types
    else:
        return set([type(arg)])


def _validate_args(args):
    """ Validates arguments. Lists and dictionaries are valid argument types,
    so you can pass *args and **dargs in directly, rather than having to
    iterate over them yourself. """
    unpassable_types = _get_unpassable_types(args)
    if unpassable_types:
        msg = "arguments of type '%s' cannot be passed to remote profilers"
        msg %= ", ".join(t.__name__ for t in unpassable_types)
        raise TypeError(msg)


class profiler_proxy(object):
    """ This is a server-side class that acts as a proxy to a real client-side
    profiler class."""

    def __init__(self, profiler_name):
        self.name = profiler_name

        # does the profiler support rebooting?
        profiler_module = common.setup_modules.import_module(
            profiler_name, "autotest_lib.client.profilers.%s" % profiler_name)
        profiler_class = getattr(profiler_module, profiler_name)
        self.supports_reboot = profiler_class.supports_reboot


    def initialize(self, *args, **dargs):
        _validate_args(args)
        _validate_args(dargs)
        self.args, self.dargs = args, dargs


    def setup(self, *args, **dargs):
        assert self.args == args and self.dargs == dargs
        # the actual setup happens lazily at start()


    def start(self, test, host=None):
        raise NotImplementedError('start not implemented')


    def stop(self, test, host=None):
        raise NotImplementedError('stop not implemented')


    def report(self, test, host=None, wait_on_client=True):
        raise NotImplementedError('report not implemented')
