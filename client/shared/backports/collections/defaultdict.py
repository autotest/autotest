'''
Backport of the defaultdict module, obtained from:
http://code.activestate.com/recipes/523034-emulate-collectionsdefaultdict/
'''

# pylint: disable=I0011,C0103


class defaultdict(dict):

    """
    collections.defaultdict is a handy shortcut added in Python 2.5 which can
    be emulated in older versions of Python. This recipe tries to backport
    defaultdict exactly and aims to be safe to subclass and extend without
    worrying if the base class is in C or is being emulated.

    http://code.activestate.com/recipes/523034-emulate-collectionsdefaultdict/
    :codeauthor: Jason Kirtland
    :license: PSF

    Changes:
    * replaced self.items() with self.iteritems() to fix Pickle bug as
    recommended by Aaron Lav
    * reformated with autopep8
    """

    def __init__(self, default_factory=None, *a, **kw):
        if (default_factory is not None and
                not hasattr(default_factory, '__call__')):
            raise TypeError('first argument must be callable')
        dict.__init__(self, *a, **kw)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        if self.default_factory is None:
            args = tuple()
        else:
            args = self.default_factory,
        return type(self), args, None, None, self.iteritems()

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return type(self)(self.default_factory, self)

    # pylint: disable=I0011,W0613
    def __deepcopy__(self, memo):
        import copy
        return type(self)(self.default_factory,
                          copy.deepcopy(self.iteritems()))

    def __repr__(self):
        return 'defaultdict(%s, %s)' % (self.default_factory,
                                        dict.__repr__(self))
