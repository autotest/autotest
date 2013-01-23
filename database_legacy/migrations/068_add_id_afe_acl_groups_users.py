UP_SQL = """
ALTER TABLE afe_acl_groups_users ADD COLUMN id integer AUTO_INCREMENT NOT NULL PRIMARY KEY FIRST;
"""

DOWN_SQL = """
ALTER TABLE afe_acl_groups_users DROP COLUMN id;
"""
