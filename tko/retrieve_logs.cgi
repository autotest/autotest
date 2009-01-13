#!/usr/bin/python

import cgi, os, sys, urllib2
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.bin import utils

page = """\
Status: 302 Found
Content-Type: text/plain
Location: %s\r\n\r
"""

# Get access to directories
tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

autodir = os.path.abspath(os.path.join(tko, '..'))


def _retrieve_logs_dummy(job_path):
    pass


# Define function for retrieving logs
retrieve_logs = import_site_function(__file__,
    "autotest_lib.tko.site_retrieve_logs", "retrieve_logs",
    _retrieve_logs_dummy)


# Get form fields
form = cgi.FieldStorage(keep_blank_values=True)
# Retrieve logs
job_path = form['job'].value
job_path = os.path.join(autodir, job_path)
keyval = retrieve_logs(job_path)


def find_repository_host(job_path):
    """Find the machine holding the given logs and return a URL to the logs"""
    config = global_config.global_config
    drones = config.get_config_value('SCHEDULER', 'drones')
    results_host = config.get_config_value('SCHEDULER', 'results_host')
    drone_list = [hostname.strip() for hostname in drones.split(',')]
    results_repos = [results_host] + drone_list
    if results_repos != ['localhost']:
        for drone in results_repos:
            http_path = 'http://%s%s' % (drone, job_path)
            try:
                urllib2.urlopen(http_path)
                if drone == 'localhost':
                    return None
                return drone
            except urllib2.URLError:
                pass
        # just return the results repo if we haven't found any
        return results_host
    else:
        return None


def get_full_path(host, path):
    if host:
        prefix = 'http://' + host
    else:
        prefix = ''

    if form.has_key('jsonp_callback'):
        callback = form['jsonp_callback'].value
        return '%s/tko/jsonp_fetcher.cgi?path=%s&callback=%s' % (
            prefix, path, callback)
    else:
        return prefix + path


host = find_repository_host(job_path)
print page % get_full_path(host, job_path)
