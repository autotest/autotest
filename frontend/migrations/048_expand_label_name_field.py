UP_SQL = """
ALTER TABLE afe_labels MODIFY name varchar(750) default NULL;
"""

DOWN_SQL = """
ALTER TABLE afe_labels MODIFY name varchar(255) default NULL;
"""
