UP_SQL = """
CREATE TABLE `saved_queries` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `owner` varchar(80) NOT NULL,
    `name` varchar(100) NOT NULL,
    `url_token` longtext NOT NULL
);

"""

DOWN_SQL = """
DROP TABLE IF EXISTS `saved_queries`;
"""

def migrate_up(manager):
    manager.execute(UP_SQL)


def migrate_down(manager):
    manager.execute(DOWN_SQL)
