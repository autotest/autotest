UP_SQL = """
ALTER TABLE users ADD COLUMN `show_experimental` bool NOT NULL DEFAULT FALSE;
"""

DOWN_SQL = """
ALTER TABLE users DROP COLUMN `show_experimental`;
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
