def migrate_up(manager):
    manager.execute_script(ADD_COLUMNS)

def migrate_down(manager):
    manager.execute_script(DROP_COLUMNS)

ADD_COLUMNS = """\
DELETE FROM embedded_graphing_queries;

ALTER TABLE embedded_graphing_queries
DROP COLUMN last_accessed;

ALTER TABLE embedded_graphing_queries
ADD COLUMN (
    last_updated DATETIME NOT NULL,
    refresh_time DATETIME DEFAULT NULL,
    cached_png MEDIUMBLOB
);
"""

DROP_COLUMNS = """\
ALTER TABLE embedded_graphing_queries
DROP COLUMN last_updated;

ALTER TABLE embedded_graphing_queries
DROP COLUMN cached_png;

ALTER TABLE embedded_graphing_queries
DROP COLUMN refresh_time;

ALTER TABLE embedded_graphing_queries
ADD COLUMN (last_accessed DATETIME NOT NULL);
"""
