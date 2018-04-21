try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.database_legacy import db_utils


ORIG_NAMES = (
    'aborted_host_queue_entries',
    'acl_groups',
    'acl_groups_hosts',
    'acl_groups_users',
    'atomic_groups',
    'autotests',
    'autotests_dependency_labels',
    'host_attributes',
    'host_queue_entries',
    'hosts',
    'hosts_labels',
    'ineligible_host_queues',
    'jobs',
    'jobs_dependency_labels',
    'labels',
    'profilers',
    'recurring_run',
    'special_tasks',
    'users',
)

RENAMES_UP = dict((name, 'afe_' + name) for name in ORIG_NAMES)

RENAMES_DOWN = dict((value, key) for key, value in RENAMES_UP.items())


def migrate_up(manager):
    db_utils.rename(manager, RENAMES_UP)


def migrate_down(manager):
    db_utils.rename(manager, RENAMES_DOWN)
