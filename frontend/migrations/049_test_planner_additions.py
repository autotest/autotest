UP_SQL = """\
BEGIN;

SET storage_engine = InnoDB;

CREATE TABLE `planner_plan_host_labels` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `label_id` integer NOT NULL
)
;
ALTER TABLE `planner_plan_host_labels` ADD CONSTRAINT plan_host_labels_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_plan_host_labels` ADD CONSTRAINT plan_host_labels_label_id_fk FOREIGN KEY (`label_id`) REFERENCES `afe_labels` (`id`);


ALTER TABLE `planner_tests` ADD COLUMN `alias` varchar(255) NOT NULL;
ALTER TABLE `planner_tests` ADD CONSTRAINT `tests_plan_id_alias_unique` UNIQUE KEY (`plan_id`, `alias`);


ALTER TABLE `planner_tests` ADD COLUMN `estimated_runtime` int NOT NULL;


ALTER TABLE `planner_test_runs` ADD COLUMN `host_id` int NOT NULL;
ALTER TABLE `planner_test_runs` ADD CONSTRAINT `test_runs_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `planner_hosts` (`id`);

COMMIT;
"""

DOWN_SQL = """\
ALTER TABLE `planner_tests` DROP KEY `tests_plan_id_alias_unique`;
ALTER TABLE `planner_tests` DROP COLUMN `alias`;
ALTER TABLE `planner_tests` DROP COLUMN `estimated_runtime`;
ALTER TABLE `planner_test_runs` DROP FOREIGN KEY `test_runs_host_id_fk`;
ALTER TABLE `planner_test_runs` DROP COLUMN `host_id`;
DROP TABLE IF EXISTS `planner_plan_host_labels`;
"""
