def migrate_up(manager):
    manager.execute('ALTER TABLE host_queue_entries '
                    'ADD COLUMN `aborted` bool NOT NULL DEFAULT FALSE')
    manager.execute("UPDATE host_queue_entries SET aborted = true WHERE "
                    "status IN ('Abort', 'Aborting', 'Aborted')")


def migrate_down(manager):
    manager.execute("UPDATE host_queue_entries SET status = 'Abort' WHERE "
                    "aborted AND status != 'Aborted'")
    manager.execute('ALTER TABLE host_queue_entries DROP COLUMN `aborted`')
