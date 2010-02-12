import common
from autotest_lib.database import migrate

UP_SQL = """\
BEGIN;

SET storage_engine = InnoDB;

CREATE TABLE `planner_plans` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `name` varchar(255) NOT NULL UNIQUE,
    `label_override` varchar(255) NULL,
    `support` longtext NOT NULL,
    `complete` bool NOT NULL,
    `dirty` bool NOT NULL,
    `initialized` bool NOT NULL
)
;


CREATE TABLE `planner_hosts` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `host_id` integer NOT NULL,
    `complete` bool NOT NULL,
    `blocked` bool NOT NULL
)
;
ALTER TABLE `planner_hosts` ADD CONSTRAINT hosts_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_hosts` ADD CONSTRAINT hosts_host_id_fk FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`);


CREATE TABLE `planner_test_control_files` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `the_hash` varchar(40) NOT NULL UNIQUE,
    `contents` longtext NOT NULL
)
;


CREATE TABLE `planner_tests` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `control_file_id` integer NOT NULL,
    `execution_order` integer NOT NULL
)
;
ALTER TABLE `planner_tests` ADD CONSTRAINT tests_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_tests` ADD CONSTRAINT tests_control_file_id_fk FOREIGN KEY (`control_file_id`) REFERENCES `planner_test_control_files` (`id`);


CREATE TABLE `planner_test_jobs` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `test_id` integer NOT NULL,
    `afe_job_id` integer NOT NULL
)
;
ALTER TABLE `planner_test_jobs` ADD CONSTRAINT test_jobs_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_test_jobs` ADD CONSTRAINT test_jobs_test_id_fk FOREIGN KEY (`test_id`) REFERENCES `planner_tests` (`id`);
ALTER TABLE `planner_test_jobs` ADD CONSTRAINT test_jobs_afe_job_id_fk FOREIGN KEY (`afe_job_id`) REFERENCES `afe_jobs` (`id`);
CREATE TABLE `planner_bugs` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `external_uid` varchar(255) NOT NULL UNIQUE
)
;


CREATE TABLE `planner_test_runs` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `test_job_id` integer NOT NULL,
    `tko_test_id` integer(10) UNSIGNED NOT NULL,
    `status` varchar(16) NOT NULL,
    `finalized` bool NOT NULL,
    `seen` bool NOT NULL,
    `triaged` bool NOT NULL
)
;
ALTER TABLE `planner_test_runs` ADD CONSTRAINT test_runs_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_test_runs` ADD CONSTRAINT test_runs_test_job_id_fk FOREIGN KEY (`test_job_id`) REFERENCES `planner_test_jobs` (`id`);
ALTER TABLE `planner_test_runs` ADD CONSTRAINT test_runs_tko_test_id_fk FOREIGN KEY (`tko_test_id`) REFERENCES `%(tko_db_name)s`.`tko_tests` (`test_idx`);


CREATE TABLE `planner_data_types` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `name` varchar(255) NOT NULL,
    `db_table` varchar(255) NOT NULL
)
;


CREATE TABLE `planner_history` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `action_id` integer NOT NULL,
    `user_id` integer NOT NULL,
    `data_type_id` integer NOT NULL,
    `object_id` integer NOT NULL,
    `old_object_repr` longtext NOT NULL,
    `new_object_repr` longtext NOT NULL,
    `time` datetime NOT NULL
)
;
ALTER TABLE `planner_history` ADD CONSTRAINT history_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_history` ADD CONSTRAINT history_user_id_fk FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`);
ALTER TABLE `planner_history` ADD CONSTRAINT history_data_type_id_fk FOREIGN KEY (`data_type_id`) REFERENCES `planner_data_types` (`id`);


CREATE TABLE `planner_saved_objects` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id` integer NOT NULL,
    `type` varchar(16) NOT NULL,
    `name` varchar(255) NOT NULL,
    `encoded_object` longtext NOT NULL,
    UNIQUE (`user_id`, `type`, `name`)
)
;
ALTER TABLE `planner_saved_objects` ADD CONSTRAINT saved_objects_user_id_fk FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`);


CREATE TABLE `planner_custom_queries` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `query` longtext NOT NULL
)
;
ALTER TABLE `planner_custom_queries` ADD CONSTRAINT custom_queries_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);


CREATE TABLE `planner_keyvals` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `the_hash` varchar(40) NOT NULL UNIQUE,
    `key` varchar(1024) NOT NULL,
    `value` varchar(1024) NOT NULL
)
;


CREATE TABLE `planner_autoprocess` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `condition` longtext NOT NULL,
    `enabled` bool NOT NULL,
    `reason_override` varchar(255) NULL
)
;
ALTER TABLE `planner_autoprocess` ADD CONSTRAINT autoprocess_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);


CREATE TABLE `planner_plan_owners` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `plan_id` integer NOT NULL,
    `user_id` integer NOT NULL,
    UNIQUE (`plan_id`, `user_id`)
)
;
ALTER TABLE `planner_plan_owners` ADD CONSTRAINT plan_owners_plan_id_fk FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`);
ALTER TABLE `planner_plan_owners` ADD CONSTRAINT plan_owners_user_id_fk FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`);


CREATE TABLE `planner_test_run_bugs` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `testrun_id` integer NOT NULL,
    `bug_id` integer NOT NULL,
    UNIQUE (`testrun_id`, `bug_id`)
)
;
ALTER TABLE `planner_test_run_bugs` ADD CONSTRAINT test_run_bugs_testrun_id_fk FOREIGN KEY (`testrun_id`) REFERENCES `planner_test_runs` (`id`);
ALTER TABLE `planner_test_run_bugs` ADD CONSTRAINT test_run_bugs_bug_id_fk FOREIGN KEY (`bug_id`) REFERENCES `planner_bugs` (`id`);


CREATE TABLE `planner_autoprocess_labels` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `autoprocess_id` integer NOT NULL,
    `testlabel_id` integer NOT NULL,
    UNIQUE (`autoprocess_id`, `testlabel_id`)
)
;
ALTER TABLE `planner_autoprocess_labels` ADD CONSTRAINT autoprocess_labels_autoprocess_id_fk FOREIGN KEY (`autoprocess_id`) REFERENCES `planner_autoprocess` (`id`);
ALTER TABLE `planner_autoprocess_labels` ADD CONSTRAINT autoprocess_labels_testlabel_id_fk FOREIGN KEY (`testlabel_id`) REFERENCES `%(tko_db_name)s`.`tko_test_labels` (`id`);


CREATE TABLE `planner_autoprocess_keyvals` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `autoprocess_id` integer NOT NULL,
    `keyval_id` integer NOT NULL,
    UNIQUE (`autoprocess_id`, `keyval_id`)
)
;
ALTER TABLE `planner_autoprocess_keyvals` ADD CONSTRAINT autoprocess_keyvals_autoprocess_id_fk FOREIGN KEY (`autoprocess_id`) REFERENCES `planner_autoprocess` (`id`);
ALTER TABLE `planner_autoprocess_keyvals` ADD CONSTRAINT autoprocess_keyvals_keyval_id_fk FOREIGN KEY (`keyval_id`) REFERENCES `planner_keyvals` (`id`);


CREATE TABLE `planner_autoprocess_bugs` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `autoprocess_id` integer NOT NULL,
    `bug_id` integer NOT NULL,
    UNIQUE (`autoprocess_id`, `bug_id`)
)
;
ALTER TABLE `planner_autoprocess_bugs` ADD CONSTRAINT autoprocess_bugs_autoprocess_id_fk FOREIGN KEY (`autoprocess_id`) REFERENCES `planner_autoprocess` (`id`);
ALTER TABLE `planner_autoprocess_bugs` ADD CONSTRAINT autoprocess_bugs_bug_id_fk FOREIGN KEY (`bug_id`) REFERENCES `planner_bugs` (`id`);


CREATE INDEX `planner_hosts_plan_id` ON `planner_hosts` (`plan_id`);
CREATE INDEX `planner_hosts_host_id` ON `planner_hosts` (`host_id`);
CREATE INDEX `planner_tests_plan_id` ON `planner_tests` (`plan_id`);
CREATE INDEX `planner_tests_control_file_id` ON `planner_tests` (`control_file_id`);
CREATE INDEX `planner_test_jobs_plan_id` ON `planner_test_jobs` (`plan_id`);
CREATE INDEX `planner_test_jobs_test_id` ON `planner_test_jobs` (`test_id`);
CREATE INDEX `planner_test_jobs_afe_job_id` ON `planner_test_jobs` (`afe_job_id`);
CREATE INDEX `planner_test_runs_plan_id` ON `planner_test_runs` (`plan_id`);
CREATE INDEX `planner_test_runs_test_job_id` ON `planner_test_runs` (`test_job_id`);
CREATE INDEX `planner_test_runs_tko_test_id` ON `planner_test_runs` (`tko_test_id`);
CREATE INDEX `planner_history_plan_id` ON `planner_history` (`plan_id`);
CREATE INDEX `planner_history_user_id` ON `planner_history` (`user_id`);
CREATE INDEX `planner_history_data_type_id` ON `planner_history` (`data_type_id`);
CREATE INDEX `planner_saved_objects_user_id` ON `planner_saved_objects` (`user_id`);
CREATE INDEX `planner_custom_queries_plan_id` ON `planner_custom_queries` (`plan_id`);
CREATE INDEX `planner_autoprocess_plan_id` ON `planner_autoprocess` (`plan_id`);

COMMIT;
"""

DOWN_SQL = """\
DROP TABLE IF EXISTS planner_autoprocess_labels;
DROP TABLE IF EXISTS planner_autoprocess_bugs;
DROP TABLE IF EXISTS planner_autoprocess_keyvals;
DROP TABLE IF EXISTS planner_autoprocess;
DROP TABLE IF EXISTS planner_custom_queries;
DROP TABLE IF EXISTS planner_saved_objects;
DROP TABLE IF EXISTS planner_history;
DROP TABLE IF EXISTS planner_data_types;
DROP TABLE IF EXISTS planner_hosts;
DROP TABLE IF EXISTS planner_keyvals;
DROP TABLE IF EXISTS planner_plan_owners;
DROP TABLE IF EXISTS planner_test_run_bugs;
DROP TABLE IF EXISTS planner_test_runs;
DROP TABLE IF EXISTS planner_test_jobs;
DROP TABLE IF EXISTS planner_tests;
DROP TABLE IF EXISTS planner_test_control_files;
DROP TABLE IF EXISTS planner_bugs;
DROP TABLE IF EXISTS planner_plans;
"""


def migrate_up(manager):
    tko_manager = migrate.get_migration_manager(db_name='TKO', debug=False,
                                                force=False)
    if tko_manager.get_db_version() < 31:
        raise Exception('You must update the TKO database to at least version '
                        '31 before applying AUTOTEST_WEB migration 45')

    manager.execute_script(UP_SQL % dict(tko_db_name=tko_manager.get_db_name()))
