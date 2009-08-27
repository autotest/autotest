#!/usr/bin/python
"""
Read a variable in the global config for autotest
i.e. SCHEDULER.drones TKO.host
"""

import sys
import common
from autotest_lib.client.common_lib import global_config


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
            print global_config.global_config.get_config_value(section, var)
        except global_config.ConfigError:
            print "Error reading %s.%s" % (section, var)


if __name__ == '__main__':
    main(sys.argv)
