def migrate_up(manager):
    manager.execute_script(CREATE_TABLE)

def migrate_down(manager):
    manager.execute_script(DROP_TABLE)

CREATE_TABLE = """\
CREATE TABLE `recurring_run` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `job_id` integer NOT NULL REFERENCES `jobs` (`id`),
    `owner_id` integer NOT NULL REFERENCES `users` (`id`),
    `start_date` datetime NOT NULL,
    `loop_period` integer NOT NULL,
    `loop_count` integer NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
CREATE INDEX recurring_run_job_id ON `recurring_run` (`job_id`);
CREATE INDEX recurring_run_owner_id ON `recurring_run` (`owner_id`);
"""

DROP_TABLE = """\
DROP INDEX recurring_run_job_id ON `recurring_run`;
DROP TABLE IF EXISTS `recurring_run`;
"""
