UP_SQL = """
CREATE TABLE `host_attributes` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `host_id` integer NOT NULL,
    `attribute` varchar(90) NOT NULL,
    `value` varchar(300) NOT NULL,
    FOREIGN KEY (host_id) REFERENCES hosts (id),
    KEY (attribute)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
"""

DOWN_SQL = """
DROP TABLE IF EXISTS host_attributes;
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
