#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SiteHost class.

This file may be removed or left empty if no site customization is neccessary.
base_classes.py contains logic to provision for this.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

        SiteHost: Host containing site-specific customizations.
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


import base_classes
from autotest_lib.server import utils

class SiteHost(base_classes.Host):
    """
    Custom host to containing site-specific methods or attributes.
    """

    def __init__(self):
        super(SiteHost, self).__init__()
        self.serverdir = utils.get_server_dir()


    def setup(self):
        return
