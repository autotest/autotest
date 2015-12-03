#!/usr/bin/python

"""
This library / script is supposed to return a URL where the job results
requested can be found. It's primarily used by presentation layers as a
a library while that pointing users to the job results, but it can also
be used in the command line for debugging purposes.
"""

import logging
import sys
import urllib2

try:
    import autotest.common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import logging_manager, logging_config
from autotest.client.shared.settings import settings
from autotest.client import utils


DRONES = settings.get_value('SCHEDULER', 'drones')
RESULTS_HOST = settings.get_value('SCHEDULER', 'results_host')
ARCHIVE_HOST = settings.get_value('SCHEDULER', 'archive_host', default='')


class LoggingConfig(logging_config.LoggingConfig):

    """
    Used with the sole purpose of providing convenient logging setup
    for this program.
    """

    def configure_logging(self, results_dir=None, verbose=False):
        super(LoggingConfig, self).configure_logging(use_console=True,
                                                     verbose=verbose)


def _retrieve_dummy(job_path):
    '''
    Dummy function for retrieving host and logs
    '''
    pass


site_retrieve_logs = utils.import_site_function(__file__,
                                                "autotest.tko.site_retrieve_logs", "site_retrieve_logs",
                                                _retrieve_dummy)


site_find_repository_host = utils.import_site_function(__file__,
                                                       "autotest.tko.site_retrieve_logs", "site_find_repository_host",
                                                       _retrieve_dummy)


def find_repository_host(job_path):
    '''
    Find the machine holding the given logs and return a URL to the logs

    :param job_path: when this was a CGI script, this value came from the
                    'job' variable, which was usually composed of '/results/' +
                    a path such as '1-autotest' or '1-autotest/status.log'
    :type job_path: str
    :returns: a tuple with three members: protocol (such as "http"), host
              (such as "foo.bar.com") and a path such as "/results/1-autotest"
    :rtype: tuple or None
    '''
    site_repo_info = site_find_repository_host(job_path)
    if site_repo_info is not None:
        return site_repo_info

    results_repos = [RESULTS_HOST]
    for drone in DRONES.split(','):
        drone = drone.strip()
        if drone not in results_repos:
            results_repos.append(drone)

    if ARCHIVE_HOST and ARCHIVE_HOST not in results_repos:
        results_repos.append(ARCHIVE_HOST)

    for drone in results_repos:
        if drone == 'localhost':
            continue
        http_path = 'http://%s%s' % (drone, job_path)
        try:
            logging.info('Attempting to access the selected results URL: "%s"',
                         http_path)
            utils.urlopen(http_path)
            return 'http', utils.normalize_hostname(drone), job_path
        except urllib2.URLError:
            logging.error('Failed to access the selected results URL. '
                          'Reverting to usual results location')
            pass


def get_full_url(info, log_path):
    '''
    Returns the full URL of the requested log path

    :param info: a 3 element tuple such with protocol, host and path, usually
                 the output from the find_repository_host function.
    :type info: tuple
    :param log_path: when this was a CGI script, this value came from the
                    'job' variable, which was usually composed of '/results/' +
                    a path such as '1-autotest' or '1-autotest/status.log'
    :type log_path: str
    :returns: the full url of the log file or directory request
    :rtype: str
    '''
    if info is not None:
        protocol, host, path = info
        prefix = '%s://%s' % (protocol, host)
    else:
        prefix = ''
        path = log_path

    return prefix + path


def retrieve_logs(path):
    host = find_repository_host(path)
    if host is None:
        logging.info('No special host was found holding the results')

    # It's not clear what was intended here. Maybe some custom action to
    # fetch/unpack the logs?
    site_retrieve_logs(path)

    results_url = get_full_url(host, path)
    logging.info('Results url: %s', results_url)
    return results_url


if __name__ == '__main__':
    logging_manager.configure_logging(LoggingConfig(), verbose=True)

    if len(sys.argv) <= 1:
        logging.error('Usage: %s [log_path]', sys.argv[0])
        raise SystemExit

    path = sys.argv[1]
    retrieve_logs(path)
