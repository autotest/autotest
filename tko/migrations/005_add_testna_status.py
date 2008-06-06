def migrate_up(monger):
    monger.execute("INSERT INTO status (word) values ('TEST_NA')")


def migrate_down(monger):
    monger.execute("DELETE FROM status where word = 'TEST_NA'")
