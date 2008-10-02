def migrate_up(manager):
    manager.execute("""ALTER TABLE hosts
                       ADD COLUMN locked_by_id
                       INT(11) DEFAULT NULL""")
    manager.execute("""ALTER TABLE hosts
                       ADD COLUMN lock_time
                       DATETIME DEFAULT NULL""")


def migrate_down(manager):
    manager.execute('ALTER TABLE hosts DROP COLUMN locked_by_id')
    manager.execute('ALTER TABLE hosts DROP COLUMN lock_time')
