def migrate_up(manager):
    manager.execute_script(ADD_TABLE_QUERY_HISTORY)


def migrate_down(manager):
    manager.execute_script(DROP_TABLE_QUERY_HISTORY)


ADD_TABLE_QUERY_HISTORY = """
CREATE TABLE IF NOT EXISTS query_history
(uid VARCHAR(32), time_created VARCHAR(32), user_comment VARCHAR(256),
url VARCHAR(1000));
"""

DROP_TABLE_QUERY_HISTORY = """
DROP TABLE query_history;
"""
