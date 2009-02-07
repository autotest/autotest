# acl_group_id in the many2many pivot table was an old Ruby-ism which
# required a gross hack on Django 0.96 to support.  The Django name for the
# column is aclgroup_id, it requires no unsupportable hacks.

# NOTE: This is annoying the MySQL way of renaming columns.
UP_SQL = """
ALTER TABLE acl_groups_hosts CHANGE
    acl_group_id aclgroup_id int(11) default NULL;
ALTER TABLE acl_groups_users CHANGE
    acl_group_id aclgroup_id int(11) default NULL;
"""

DOWN_SQL = """
ALTER TABLE acl_groups_hosts CHANGE
    aclgroup_id acl_group_id int(11) default NULL;
ALTER TABLE acl_groups_users CHANGE
    aclgroup_id acl_group_id int(11) default NULL;
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
