import common
from autotest_lib.client.common_lib import enum, utils


def _site_host_actions_dummy():
    return []

_site_host_actions = utils.import_site_function(
        __file__, 'autotest_lib.frontend.planner.site_failure_actions',
        'site_host_actions', _site_host_actions_dummy)

HostAction = enum.Enum(
        string_values=True,
        *(_site_host_actions() + ['Block', 'Unblock', 'Reinstall']))


TestAction = enum.Enum('Skip', 'Rerun', string_values=True)
