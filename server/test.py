# Copyright Martin J. Bligh, Andy Whitcroft, 2007
#
# Define the server-side test class
#

import os

from autotest_lib.client.common_lib import test as common_test


class test(common_test.base_test):
    pass


def runtest(job, url, tag, args, dargs):
    common_test.runtest(job, url, tag, args, dargs,
                        locals(), globals())
