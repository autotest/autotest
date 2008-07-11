CREATE_TABLES_SQL = """
CREATE TABLE `test_labels` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `name` varchar(80) NOT NULL,
    `description` longtext NOT NULL
);

CREATE TABLE `test_labels_tests` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `testlabel_id` integer NOT NULL REFERENCES `test_labels` (`id`),
    `test_id` integer NOT NULL REFERENCES `tests` (`test_idx`),
    UNIQUE (`testlabel_id`, `test_id`)
);
"""

DROP_TABLES_SQL = """
DROP TABLE IF EXISTS `test_labels`;
DROP TABLE IF EXISTS `test_labels_tests`;
"""


def migrate_up(manager):
    manager.execute_script(CREATE_TABLES_SQL)


def migrate_down(manager):
    manager.execute_script(DROP_TABLES_SQL)
