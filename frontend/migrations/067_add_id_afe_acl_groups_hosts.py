UP_SQL = """
ALTER TABLE afe_acl_groups_hosts ADD COLUMN id integer AUTO_INCREMENT NOT NULL PRIMARY KEY FIRST;
"""

DOWN_SQL = """
ALTER TABLE afe_acl_groups_hosts DROP COLUMN id;
"""
