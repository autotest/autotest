UP_SQL = """
INSERT INTO afe_acl_groups (id, name) VALUES (1, 'Everyone') ON DUPLICATE KEY UPDATE name='Everyone';
"""

# Since this used to be a value INSERTED by Django fixtures, do not remove it
# when downgrading versions
DOWN_SQL = """
"""
