import os

required_tables = ('acl_groups', 'acl_groups_hosts', 'acl_groups_users',
                   'autotests', 'host_queue_entries', 'hosts', 'hosts_labels',
                   'ineligible_host_queues', 'jobs', 'labels', 'users')


def migrate_up(manager):
    rows = manager.execute("SHOW TABLES")
    tables = [row[0] for row in rows]
    db_initialized = True
    for table in required_tables:
        if table not in tables:
            db_initialized = False
            break
    if not db_initialized:
        if not manager.force:
            response = raw_input(
                'Your autotest_web database does not appear to be '
                'initialized.  Do you want to recreate it (this will '
                'result in loss of any existing data) (yes/No)? ')
            if response != 'yes':
                raise Exception('User has chosen to abort migration')

        manager.execute_script(CREATE_DB_SQL)

    manager.create_migrate_table()


def migrate_down(manager):
    manager.execute_script(DROP_DB_SQL)


CREATE_DB_SQL = """\
--
-- Table structure for table `acl_groups`
--

DROP TABLE IF EXISTS `acl_groups`;
CREATE TABLE `acl_groups` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) default NULL,
  `description` varchar(255) default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `acl_groups_hosts`
--

DROP TABLE IF EXISTS `acl_groups_hosts`;
CREATE TABLE `acl_groups_hosts` (
  `acl_group_id` int(11) default NULL,
  `host_id` int(11) default NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `acl_groups_users`
--

DROP TABLE IF EXISTS `acl_groups_users`;
CREATE TABLE `acl_groups_users` (
  `acl_group_id` int(11) default NULL,
  `user_id` int(11) default NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `autotests`
--

DROP TABLE IF EXISTS `autotests`;
CREATE TABLE `autotests` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) default NULL,
  `test_class` varchar(255) default NULL,
  `params` varchar(255) default NULL,
  `description` text,
  `test_type` int(11) default NULL,
  `path` varchar(255) default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS `host_queue_entries`;
CREATE TABLE `host_queue_entries` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) default NULL,
  `host_id` int(11) default NULL,
  `priority` int(11) default NULL,
  `status` varchar(255) default NULL,
  `created_on` datetime default NULL,
  `meta_host` int(11) default NULL,
  `active` tinyint(1) default '0',
  `complete` tinyint(1) default '0',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `hosts`
--

DROP TABLE IF EXISTS `hosts`;
CREATE TABLE `hosts` (
  `id` int(11) NOT NULL auto_increment,
  `hostname` varchar(255) default NULL,
  `locked` tinyint(1) default '0',
  `synch_id` int(11) default NULL,
  `status` varchar(255) default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `hosts_labels`
--

DROP TABLE IF EXISTS `hosts_labels`;
CREATE TABLE `hosts_labels` (
  `host_id` int(11) default NULL,
  `label_id` int(11) default NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `ineligible_host_queues`
--

DROP TABLE IF EXISTS `ineligible_host_queues`;
CREATE TABLE `ineligible_host_queues` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) default NULL,
  `host_id` int(11) default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `jobs`
--

DROP TABLE IF EXISTS `jobs`;
CREATE TABLE `jobs` (
  `id` int(11) NOT NULL auto_increment,
  `owner` varchar(255) default NULL,
  `name` varchar(255) default NULL,
  `priority` int(11) default NULL,
  `control_file` text,
  `control_type` int(11) default NULL,
  `kernel_url` varchar(255) default NULL,
  `status` varchar(255) default NULL,
  `created_on` datetime default NULL,
  `submitted_on` datetime default NULL,
  `synch_type` int(11) default NULL,
  `synch_count` int(11) default NULL,
  `synchronizing` tinyint(1) default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `labels`
--

DROP TABLE IF EXISTS `labels`;
CREATE TABLE `labels` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) default NULL,
  `kernel_config` varchar(255) default NULL,
  `platform` tinyint(1) default '0',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int(11) NOT NULL auto_increment,
  `login` varchar(255) default NULL,
  `access_level` int(11) default '0',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
"""


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
