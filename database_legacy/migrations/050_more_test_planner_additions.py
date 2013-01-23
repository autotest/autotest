UP_SQL = """
ALTER TABLE `planner_test_runs` ADD CONSTRAINT `test_runs_unique` UNIQUE KEY (`plan_id`, `test_job_id`, `tko_test_id`, `host_id`);

ALTER TABLE `planner_tests` ADD COLUMN `is_server` tinyint(1) DEFAULT 1;

ALTER TABLE `planner_hosts` ADD COLUMN `added_by_label` tinyint(1) DEFAULT 0;
"""

DOWN_SQL = """
ALTER TABLE `planner_hosts` DROP COLUMN `added_by_label`;
ALTER TABLE `planner_tests` DROP COLUMN `is_server`;
ALTER TABLE `planner_test_runs` DROP KEY `test_runs_unique`;
"""
