def migrate_up(manager):
    manager.execute_script(CLEAN_DATABASE)
    manager.execute(ADD_HOST_QUEUE_DELETED_COLUMN)
    manager.execute(DROP_DEFAULT)

def migrate_down(manager):
    manager.execute(DROP_HOST_QUEUE_DELETED_COLUMN)

CLEAN_DATABASE = """DELETE FROM acl_groups_hosts
                    WHERE host_id IN
                        (SELECT id FROM hosts WHERE invalid = TRUE);

                    DELETE FROM ineligible_host_queues
                    WHERE host_id IN
                        (SELECT id FROM hosts WHERE invalid = TRUE);

                    UPDATE host_queue_entries
                    SET status = 'Abort'
                    WHERE host_id IN
                        (SELECT id FROM hosts WHERE invalid = TRUE)
                        AND active = TRUE;

                    UPDATE host_queue_entries
                    SET status = 'Aborted', complete = TRUE
                    WHERE host_id IN
                        (SELECT id FROM hosts WHERE invalid = TRUE)
                        AND active = FALSE AND complete = FALSE;

                    DELETE FROM hosts_labels
                    WHERE host_id IN
                        (SELECT id FROM hosts WHERE invalid = TRUE);"""

DROP_HOST_QUEUE_DELETED_COLUMN = """ALTER TABLE host_queue_entries
                                    DROP COLUMN deleted"""

ADD_HOST_QUEUE_DELETED_COLUMN = """ALTER TABLE host_queue_entries
                                   ADD COLUMN deleted BOOLEAN
                                       NOT NULL DEFAULT FALSE"""

DROP_DEFAULT = """ALTER TABLE host_queue_entries
                  ALTER COLUMN deleted DROP DEFAULT"""
