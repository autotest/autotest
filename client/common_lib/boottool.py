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

import os, sys, imp

#
# This performs some import magic, to import the boottool cli as a module
#
CURRENT_DIRECTORY = os.path.dirname(sys.modules[__name__].__file__)
CLIENT_DIRECTORY = os.path.abspath(os.path.join(CURRENT_DIRECTORY, ".."))
BOOTTOOL_CLI_PATH = os.path.join(CLIENT_DIRECTORY, "tools", "boottool")
imp.load_source("boottool_cli", BOOTTOOL_CLI_PATH)
from boottool_cli import Grubby


class boottool(Grubby):
    """
    Client site side boottool wrapper.

    Inherits all functionality from boottool(.py) CLI app
    """
    def __init__(self, path='/sbin/grubby'):
        Grubby.__init__(self, path)
