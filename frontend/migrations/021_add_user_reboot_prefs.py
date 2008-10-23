UP_SQL = """
ALTER TABLE users ADD COLUMN `reboot_before` smallint NOT NULL;
ALTER TABLE users ADD COLUMN `reboot_after` smallint NOT NULL;
UPDATE users SET reboot_before=1, reboot_after=2;
"""


DOWN_SQL = """
ALTER TABLE users DROP COLUMN reboot_before;
ALTER TABLE users DROP COLUMN reboot_after;
"""


def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
