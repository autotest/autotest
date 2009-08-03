#!/usr/bin/python

# change_protection_level.py "No protection" machine1 machine2 machine3

import sys, optparse, traceback, pwd, os
import common
from autotest_lib.cli import rpc, host

usage = 'usage: %prog [options] new_protection_level machine1 machine2 ...'
parser = optparse.OptionParser(usage=usage)
parser.add_option('-w', '--web',
                  help='Autotest server to use (i.e. "autotest")')

options, leftover_args = parser.parse_args()
assert len(leftover_args) > 1, 'Must pass protection level and hosts'
protection_level = leftover_args[0]

user = pwd.getpwuid(os.getuid())[0]
autotest_host = rpc.get_autotest_server(options.web)
afe_proxy = rpc.afe_comm(autotest_host, '/afe/server/noauth/rpc/')

hosts = afe_proxy.run('get_hosts', hostname__in=leftover_args[1:])
for host in hosts:
    try:
        afe_proxy.run('modify_host', host['id'], protection=protection_level)
    except Exception, exc:
        print 'For host %s:', host['hostname']
        traceback.print_exc()
    else:
        print 'Host %s succeeded' % host['hostname']

print 'Invalid hosts:'
print ','.join(set(leftover_args[1:]) - set(host['hostname'] for host in hosts))
