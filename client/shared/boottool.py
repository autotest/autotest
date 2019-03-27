'''
boottool client-side module.

This module provides an API for client side tests that need to manipulate
boot entries. It's based on the rewrite of boottool, now python and grubby
based. It aims to be keep API compatibility with the older version, except
from XEN support which has been removed. We'll gladly accept patches that
provide full coverage for this mode/feature.

Copyright 2009 Google Inc.
Copyright 2012 Red Hat, Inc.

Released under the GPL v2
'''

from autotest.client.shared import error
from autotest.client.tools.boottool import GRUBBY_DEFAULT_SYSTEM_PATH
from autotest.client.tools.boottool import Grubby, install_grubby_if_necessary


class boottool(Grubby):

    """
    Client site side boottool wrapper.

    Inherits all functionality from boottool(.py) CLI app (lazily).
    """

    def __init__(self, path=None):
        self.instantiated = False
        if path is None:
            path = GRUBBY_DEFAULT_SYSTEM_PATH
        self.path = path

    def _init_on_demand(self):
        if not self.instantiated:
            try:
                install_grubby_if_necessary()
                Grubby.__init__(self, self.path)
                self.instantiated = True
            except Exception as e:
                raise error.JobError("Unable to instantiate boottool: %s" % e)

    def __getattr__(self, name):
        self._init_on_demand()
        return Grubby.__getattribute__(self, name)
