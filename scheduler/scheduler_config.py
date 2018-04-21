try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared.settings import settings

CONFIG_SECTION = 'SCHEDULER'


class SchedulerConfig(object):

    """
    Contains configuration that can be changed during scheduler execution.
    """
    FIELDS = {'max_processes_per_drone': 'max_processes_per_drone',
              'max_processes_started_per_cycle': 'max_jobs_started_per_cycle',
              'clean_interval': 'clean_interval_minutes',
              'max_parse_processes': 'max_parse_processes',
              'tick_pause_sec': 'tick_pause_sec',
              'max_transfer_processes': 'max_transfer_processes',
              'secs_to_wait_for_atomic_group_hosts':
              'secs_to_wait_for_atomic_group_hosts',
              'reverify_period_minutes': 'reverify_period_minutes',
              'reverify_max_hosts_at_once': 'reverify_max_hosts_at_once',
              }

    def __init__(self):
        self.read_config()

    def read_config(self):
        settings.parse_config_file()
        for field, config_option in self.FIELDS.items():
            setattr(self, field, settings.get_value(CONFIG_SECTION,
                                                    config_option,
                                                    type=int))


config = SchedulerConfig()
