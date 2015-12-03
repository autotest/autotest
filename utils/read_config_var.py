#!/usr/bin/python
"""
Read a variable in the global config for autotest
i.e. SCHEDULER.drones TKO.host
"""

import sys
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared.settings import settings, SettingsError


def usage():
    print ("Usage: ./read_var_config.py SECTION.variable.\n"
           "e.g. ./read_var_config.py SCHEDULER.drones TKO.host.\n")
    sys.exit(1)


def main(args):

    if len(args) <= 1:
        usage()

    entries = args[1:]

    for entry in entries:
        try:
            section, var = entry.split('.')
        except ValueError:
            print "Invalid SECTION.varable supplied: " + entry
            usage()

        try:
            print settings.get_value(section, var)
        except SettingsError:
            print "Error reading %s.%s" % (section, var)


if __name__ == '__main__':
    main(sys.argv)
