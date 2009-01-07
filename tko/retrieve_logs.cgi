#!/usr/bin/python

import cgi, os, sys, urllib2
import common
from autotest_lib.client.common_lib import global_config

page = """\
Status: 302 Found
Content-Type: text/plain
Location: %s\r\n\r
"""

# Get access to directories
tko = os.path.dirname(os.path.realpath(os.path.abspath(sys.argv[0])))
sys.path.insert(0, tko)

autodir = os.path.abspath(os.path.join(tko, '..'))

# Define function for retrieving logs
try:
    import site_retrieve_logs
    retrieve_logs = site_retrieve_logs.retrieve_logs
    del site_retrieve_logs
except ImportError:
    def retrieve_logs(job_path):
        pass

# Get form fields
form = cgi.FieldStorage(keep_blank_values=True)
# Retrieve logs
job_path = form['job'].value[1:]
job_path = os.path.join(autodir, job_path)
keyval = retrieve_logs(job_path)


def find_repo(job_path):
    """Find the machine holding the given logs and return a URL to the logs"""
    config = global_config.global_config
    drones = config.get_config_value('SCHEDULER', 'drones')
    results_host = config.get_config_value('SCHEDULER', 'results_host')
    if drones and results_host and results_host != 'localhost':
        drone_list = [hostname.strip() for hostname in drones.split(',')]
        results_repos = [results_host] + drone_list
        for drone in results_repos:
            http_path = 'http://%s%s' % (drone, form['job'].value)
            try:
                urllib2.urlopen(http_path).read()
                return http_path
            except urllib2.URLError:
                pass
        # just return the results repo if we haven't found any
        return 'http://%s%s' % (results_host, form['job'].value)
    else:
    # Local
        return form['job'].value


print page % find_repo(job_path)
