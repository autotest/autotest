INDEXES = (
    ('acl_groups_hosts', 'host_id'),
    ('acl_groups_hosts', 'acl_group_id'),
    ('acl_groups_users', 'user_id'),
    ('acl_groups_users', 'acl_group_id'),
)

def get_index_name(table, field):
    return table + '_' + field


def migrate_up(manager):
    for table, field in INDEXES:
        manager.execute('CREATE INDEX %s ON %s (%s)' %
                        (get_index_name(table, field), table, field))


def migrate_down(manager):
    for table, field in INDEXES:
        manager.execute('DROP INDEX %s ON %s' %
                        (get_index_name(table, field), table))
