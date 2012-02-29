# Copyright 2009 Google Inc. Released under the GPL v2

import re, os, sys, imp

#
# This performs some import magic, to import the boottool cli as a module
# For now, the boottool cli is named boottool.py, but once it gets feature
# complete and boottool(.pl) gets removed, then we'll renamed it boottool
# and this import code will be even more necessary
#
dirname = os.path.dirname(sys.modules[__name__].__file__)
client_dir = os.path.abspath(os.path.join(dirname, ".."))
boottool_cli_path = os.path.join(client_dir, "tools", "boottool.py")
imp.load_source("boottool_cli", boottool_cli_path)
from boottool_cli import Grubby


class boottool(Grubby):
    """
    Common class for the client and server side boottool wrappers.
    """

    def __init__(self, path='/sbin/grubby'):
        Grubby.__init__(self, path)
        self._xen_mode = False


    def enable_xen_mode(self):
        """
        Enables xen mode. Future operations will assume xen is being used.
        """
        self._xen_mode = True


    def disable_xen_mode(self):
        """
        Disables xen mode.
        """
        self._xen_mode = False


    def get_xen_mode(self):
        """
        Returns a boolean with the current status of xen mode.
        """
        return self._xen_mode
