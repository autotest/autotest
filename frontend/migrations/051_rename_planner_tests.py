UP_SQL = """
ALTER TABLE `planner_tests` RENAME TO `planner_test_configs`;

ALTER TABLE `planner_test_jobs` DROP FOREIGN KEY `test_jobs_test_id_fk`;
ALTER TABLE `planner_test_jobs` DROP KEY `planner_test_jobs_test_id`;

ALTER TABLE `planner_test_jobs` CHANGE COLUMN
`test_id` `test_config_id` INT NOT NULL;

ALTER TABLE `planner_test_jobs` ADD CONSTRAINT `test_jobs_test_config_id_fk`
FOREIGN KEY `planner_test_jobs_test_config_id`
(`test_config_id`) REFERENCES `planner_test_configs` (`id`);
"""

DOWN_SQL = """
ALTER TABLE `planner_test_configs` RENAME TO `planner_tests`;

ALTER TABLE `planner_test_jobs` DROP FOREIGN KEY `test_jobs_test_config_id_fk`;
ALTER TABLE `planner_test_jobs` DROP KEY `planner_test_jobs_test_config_id`;

ALTER TABLE `planner_test_jobs` CHANGE COLUMN
`test_config_id` `test_id` INT NOT NULL;

ALTER TABLE `planner_test_jobs` ADD CONSTRAINT `test_jobs_test_id_fk`
FOREIGN KEY `planner_test_jobs_test_id`
(`test_id`) REFERENCES `planner_tests` (`id`);
"""
