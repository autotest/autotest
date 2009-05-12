UP_SQL = """
ALTER TABLE test_attributes
    ADD COLUMN id integer NOT NULL AUTO_INCREMENT PRIMARY KEY,
    ADD COLUMN user_created bool NOT NULL DEFAULT FALSE;
"""

DOWN_SQL = """
ALTER TABLE test_attributes DROP COLUMN user_created, DROP COLUMN id;
"""
