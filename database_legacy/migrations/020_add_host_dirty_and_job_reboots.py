UP_SQL = """
ALTER TABLE hosts ADD COLUMN `dirty` bool NOT NULL;
ALTER TABLE jobs ADD COLUMN `reboot_before` smallint NOT NULL;
ALTER TABLE jobs ADD COLUMN `reboot_after` smallint NOT NULL;
"""

DOWN_SQL = """
ALTER TABLE hosts DROP COLUMN `dirty`;
ALTER TABLE jobs DROP COLUMN `reboot_before`;
ALTER TABLE jobs DROP COLUMN `reboot_after`;
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
