def migrate_up(manager):
    manager.execute(CREATE_TABLE)

def migrate_down(manager):
    manager.execute("DROP TABLE IF EXISTS `aborted_host_queue_entries`")

CREATE_TABLE = """\
CREATE TABLE `aborted_host_queue_entries` (
    `queue_entry_id` integer NOT NULL PRIMARY KEY,
    `aborted_by_id` integer NOT NULL,
    `aborted_on` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1
"""
