INDEXES = (
    ('ineligible_host_queues', 'job_id'),
    ('ineligible_host_queues', 'host_id'),
    ('host_queue_entries', 'job_id'),
    ('host_queue_entries', 'host_id'),
    ('host_queue_entries', 'meta_host'),
    ('hosts_labels', 'label_id'),
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
