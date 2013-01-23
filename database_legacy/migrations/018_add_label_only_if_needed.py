CREATE_MANY2MANY_TABLES = """
CREATE TABLE `autotests_dependency_labels` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `test_id` integer NOT NULL REFERENCES `autotests` (`id`),
    `label_id` integer NOT NULL REFERENCES `labels` (`id`),
    UNIQUE (`test_id`, `label_id`)
);
CREATE TABLE `jobs_dependency_labels` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `job_id` integer NOT NULL REFERENCES `jobs` (`id`),
    `label_id` integer NOT NULL REFERENCES `labels` (`id`),
    UNIQUE (`job_id`, `label_id`)
);
"""

def migrate_up(manager):
    manager.execute('ALTER TABLE labels '
                    'ADD COLUMN only_if_needed bool NOT NULL')
    manager.execute_script(CREATE_MANY2MANY_TABLES)

def migrate_down(manager):
    manager.execute('ALTER TABLE labels DROP COLUMN only_if_needed')
    manager.execute('DROP TABLE IF EXISTS `autotests_dependency_labels`')
    manager.execute('DROP TABLE IF EXISTS `jobs_dependency_labels`')
