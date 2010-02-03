#!/usr/bin/python

import common, logging
from autotest_lib.client.common_lib import global_config, utils
from autotest_lib.scheduler import drone_utility

class BaseResultsArchiver(object):
    def archive_results(self, path):
        results_host = global_config.global_config.get_config_value(
                'SCHEDULER', 'results_host', default=None)
        if not results_host or results_host == 'localhost':
            return

        if not path.endswith('/'):
            path += '/'

        logging.info('Archiving %s to %s', path, results_host)
        utility = drone_utility.DroneUtility()
        utility.sync_send_file_to(results_host, path, path, can_fail=True)


ResultsArchiver = utils.import_site_class(
        __file__, 'autotest_lib.scheduler.site_archive_results',
        'SiteResultsArchiver', BaseResultsArchiver)
