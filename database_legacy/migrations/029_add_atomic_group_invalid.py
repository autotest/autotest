def migrate_up(manager):
    manager.execute('ALTER TABLE atomic_groups ADD `invalid` bool NOT NULL')


def migrate_down(manager):
    manager.execute('ALTER TABLE atomic_groups DROP invalid')
