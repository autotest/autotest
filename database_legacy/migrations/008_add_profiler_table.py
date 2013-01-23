def migrate_up(manager):
    manager.execute_script(CREATE_TABLE)


def migrate_down(manager):
    manager.execute("DROP TABLE IF EXISTS 'profilers'")


CREATE_TABLE = """\
CREATE TABLE `profilers` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) NOT NULL,
  `description` longtext NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1
"""
