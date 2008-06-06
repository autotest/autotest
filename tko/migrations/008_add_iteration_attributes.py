def migrate_up(manager):
    manager.execute_script(CREATE_TABLE_SQL)

def migrate_down(manager):
    manager.execute_script(DROP_TABLE_SQL)


CREATE_TABLE_SQL = """
-- test iteration attributes (key value pairs at an iteration level)
CREATE TABLE iteration_attributes (
test_idx int(10) unsigned NOT NULL,     -- ref to test table
FOREIGN KEY (test_idx) REFERENCES tests(test_idx) ON DELETE CASCADE,
iteration INTEGER,                      -- integer
attribute VARCHAR(30),                  -- attribute name (e.g. 'run_id')
value VARCHAR(100),                     -- attribute value
KEY `test_idx` (`test_idx`)
) TYPE=InnoDB;
"""

DROP_TABLE_SQL = """
DROP TABLE iteration_attributes;
"""
