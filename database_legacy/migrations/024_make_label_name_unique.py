UP_SQL = """
ALTER TABLE labels MODIFY name VARCHAR(255) UNIQUE;
"""

DOWN_SQL = """
ALTER TABLE labels MODIFY name VARCHAR(255);
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
