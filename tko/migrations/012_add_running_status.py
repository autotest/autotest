def migrate_up(manager):
    manager.execute("INSERT INTO status (word) values ('RUNNING')")


def migrate_down(manager):
    manager.execute("DELETE FROM status where word = 'RUNNING'")
