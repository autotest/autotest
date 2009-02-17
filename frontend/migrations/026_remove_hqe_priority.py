UP_SQL = """
ALTER TABLE `host_queue_entries` DROP COLUMN `priority`;
"""

DOWN_SQL = """
ALTER TABLE `host_queue_entries` ADD COLUMN `priority` int(11) default NULL
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
