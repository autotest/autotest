def migrate_up(manager):
    manager.execute('ALTER TABLE hosts ADD `invalid` bool NOT NULL')
    manager.execute('ALTER TABLE labels ADD `invalid` bool NOT NULL')


def migrate_down(manager):
    manager.execute('ALTER TABLE hosts DROP invalid')
    manager.execute('ALTER TABLE labels DROP invalid')
