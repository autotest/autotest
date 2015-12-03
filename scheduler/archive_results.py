#!/usr/bin/python

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import logging

from autotest.client.shared import utils
from autotest.client.shared.settings import settings
from autotest.scheduler import drone_utility


class BaseResultsArchiver(object):

    def archive_results(self, path):
        results_host = settings.get_value('SCHEDULER', 'results_host',
                                          default=None)
        if not results_host or results_host == 'localhost':
            return

        if not path.endswith('/'):
            path += '/'

        logging.info('Archiving %s to %s', path, results_host)
        utility = drone_utility.DroneUtility()
        utility.sync_send_file_to(results_host, path, path, can_fail=True)


ResultsArchiver = utils.import_site_class(
    __file__, 'autotest.scheduler.site_archive_results',
    'SiteResultsArchiver', BaseResultsArchiver)
