def migrate_up(manager):
    raise Exception('migrate.py should be migrating directly to schema 51 '
                    'instead of running migration 1...')


def migrate_down(manager):
    manager.execute_script(DROP_DB_SQL)


DROP_DB_SQL = """\
DROP TABLE IF EXISTS `acl_groups`;
DROP TABLE IF EXISTS `acl_groups_hosts`;
DROP TABLE IF EXISTS `acl_groups_users`;
DROP TABLE IF EXISTS `autotests`;
DROP TABLE IF EXISTS `host_queue_entries`;
DROP TABLE IF EXISTS `hosts`;
DROP TABLE IF EXISTS `hosts_labels`;
DROP TABLE IF EXISTS `ineligible_host_queues`;
DROP TABLE IF EXISTS `jobs`;
DROP TABLE IF EXISTS `labels`;
DROP TABLE IF EXISTS `users`;
"""
