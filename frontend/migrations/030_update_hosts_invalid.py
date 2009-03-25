def migrate_up(manager):
    manager.execute("ALTER TABLE hosts MODIFY invalid TINYINT(1) DEFAULT 0")


def migrate_down(manager):
    manager.execute("ALTER TABLE hosts MODIFY invalid TINYINT(1) DEFAULT NULL")
