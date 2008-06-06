def migrate_up(manger):
    manger.execute('CREATE INDEX hosts_labels_host_id ON hosts_labels '
                   '(host_id)')


def migrate_down(manger):
    manger.execute('DROP INDEX hosts_labels_host_id ON hosts_labels')
