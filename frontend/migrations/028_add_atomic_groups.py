def migrate_up(manager):
    manager.execute_script(CREATE_TABLE)
    manager.execute("ALTER TABLE labels ADD `atomic_group_id` "
                    "INT(11) DEFAULT NULL ")
    manager.execute("ALTER TABLE labels ADD CONSTRAINT FOREIGN KEY "
                    "(`atomic_group_id`) REFERENCES `atomic_groups` (`id`) "
                    "ON DELETE NO ACTION")
    manager.execute("ALTER TABLE host_queue_entries ADD `atomic_group_id` "
                    "INT(11) DEFAULT NULL")
    manager.execute("ALTER TABLE host_queue_entries ADD CONSTRAINT FOREIGN KEY "
                    "(`atomic_group_id`) REFERENCES `atomic_groups` (`id`) "
                    "ON DELETE NO ACTION")


def migrate_down(manager):
    manager.execute("ALTER TABLE host_queue_entries REMOVE `atomic_group_id`")
    manager.execute("ALTER TABLE labels REMOVE `atomic_group_id`")
    manager.execute("DROP TABLE IF EXISTS `atomic_groups`")


CREATE_TABLE = """\
CREATE TABLE `atomic_groups` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) NOT NULL,
  `description` longtext DEFAULT NULL,
  `max_number_of_machines` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1
"""
