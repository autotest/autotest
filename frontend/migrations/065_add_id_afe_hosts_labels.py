UP_SQL = """
ALTER TABLE afe_hosts_labels ADD COLUMN id integer AUTO_INCREMENT NOT NULL PRIMARY KEY FIRST;
"""

DOWN_SQL = """
ALTER TABLE afe_hosts_labels DROP COLUMN id;
"""
