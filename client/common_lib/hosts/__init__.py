# Copyright 2009 Google Inc. Released under the GPL v2

"""This is a convenience module to import all available types of hosts.

Implementation details:
You should 'import hosts' instead of importing every available host module.
"""

from autotest_lib.client.common_lib import utils
import base_classes

Host = utils.import_site_class(
    __file__, "autotest_lib.client.common_lib.hosts.site_host", "SiteHost",
    base_classes.Host)
