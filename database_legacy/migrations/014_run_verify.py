def migrate_up(manager):
    manager.execute('ALTER TABLE host_queue_entries ADD run_verify SMALLINT DEFAULT 1')


def migrate_down(manager):
    manager.execute('ALTER TABLE host_queue_entries DROP run_verify')
