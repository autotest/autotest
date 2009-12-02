#!/usr/bin/python

import cgi, os, sys, urllib2
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.bin import utils
from autotest_lib.frontend.afe.json_rpc import serviceHandler

_PAGE = """\
Status: 302 Found
Content-Type: text/plain
Location: %s\r\n\r
"""

# Define function for retrieving logs
def _retrieve_logs_dummy(job_path):
    pass

site_retrieve_logs = utils.import_site_function(__file__,
    "autotest_lib.tko.site_retrieve_logs", "site_retrieve_logs",
    _retrieve_logs_dummy)

site_find_repository_host = utils.import_site_function(__file__,
    "autotest_lib.tko.site_retrieve_logs", "site_find_repository_host",
    _retrieve_logs_dummy)


form = cgi.FieldStorage(keep_blank_values=True)
# determine if this is a JSON-RPC request.  we support both so that the new TKO
# client can use its RPC client code, but the old TKO can still use simple GET
# params.
_is_json_request = form.has_key('callback')

def _get_requested_path():
    if _is_json_request:
        request_data = form['request'].value
        request = serviceHandler.ServiceHandler.translateRequest(request_data)
        parameters = request['params'][0]
        return parameters['path']

    return form['job'].value


def find_repository_host(job_path):
    """Find the machine holding the given logs and return a URL to the logs"""
    config = global_config.global_config
    drones = config.get_config_value('SCHEDULER', 'drones')
    results_host = config.get_config_value('SCHEDULER', 'results_host')
    archive_host = config.get_config_value('SCHEDULER', 'archive_host',
                                            default='')
    results_repos = [results_host]
    for drone in drones.split(','):
        drone = drone.strip()
        if drone not in results_repos:
            results_repos.append(drone)

    if archive_host and archive_host not in results_repos:
        results_repos.append(archive_host)

    for drone in results_repos:
        if drone == 'localhost':
            continue
        http_path = 'http://%s%s' % (drone, job_path)
        try:
            utils.urlopen(http_path)
            return drone
        except urllib2.URLError:
            pass

    return site_find_repository_host(log_path)


def get_full_url(host, path):
    if host:
        if ':' in host:
            host, port = host.split(':')
            prefix = 'http://%s:%s' % (utils.normalize_hostname(host), port)
        else:
            prefix = 'http://%s' % utils.normalize_hostname(host)
    else:
        prefix = ''

    if _is_json_request:
        return '%s/tko/jsonp_fetcher.cgi?%s' % (prefix,
                                                os.environ['QUERY_STRING'])
    else:
        return prefix + path


log_path = _get_requested_path()
host = find_repository_host(log_path)
site_retrieve_logs(log_path)
print _PAGE % get_full_url(host, log_path)
