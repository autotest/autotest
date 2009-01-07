import common
from autotest_lib.client.common_lib import global_config

CONFIG_SECTION = 'SCHEDULER'

class SchedulerConfig(object):
    """
    Contains configuration that can be changed during scheduler execution.
    """
    FIELDS = {'max_running_processes' : 'max_running_jobs',
              'max_processes_started_per_cycle' : 'max_jobs_started_per_cycle',
              'clean_interval' : 'clean_interval_minutes',
              'synch_job_start_timeout_minutes' :
                  'synch_job_start_timeout_minutes',
              'max_parse_processes' : 'max_parse_processes',
              'tick_pause_sec' : 'tick_pause_sec',
              'max_transfer_processes' : 'max_transfer_processes',
             }

    def __init__(self):
        self.read_config()


    def read_config(self):
        config = global_config.global_config
        config.parse_config_file()
        for field, config_option in self.FIELDS.iteritems():
            setattr(self, field, config.get_config_value(CONFIG_SECTION,
                                                         config_option,
                                                         type=int))

config = SchedulerConfig()
