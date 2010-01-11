#!/usr/bin/python

"""
Send all Repair Failed hosts that the user running this script has access to
back into Verifying.  (Only hosts ACL accessable to the user)

Suggested use: Run this as an occasional cron job to re-check if Repair Failed
hosts have overcome whatever issue caused the failure and are useful again.
"""

import optparse, os, sys

import common
from autotest_lib.server import frontend


def main():
    parser = optparse.OptionParser(usage='%prog [options]\n\n' +
                                   __doc__.strip())
    parser.add_option('-w', dest='server', default='autotest',
                      help='Hostname of the autotest frontend RPC server.')
    parser.add_option('-b', dest='label', default=None, type=str,
                      help='A label to restrict the set of hosts reverified.')
    options, unused_args = parser.parse_args(sys.argv)

    afe_client = frontend.AFE(debug=False, server=options.server)
    hostnames = afe_client.reverify_hosts(status='Repair Failed',
                                          label=options.label)
    # The old RPC interface didn't return anything.
    # A more recent one returns a list of hostnames to make this message useful.
    if hostnames:
        print 'The following Repair Failed hosts on', options.server,
        print 'will be reverified:'
        print ' '.join(hostnames)
    else:
        print 'Repair Failed hosts on', options.server, 'will be reverified.'


if __name__ == '__main__':
    main()
