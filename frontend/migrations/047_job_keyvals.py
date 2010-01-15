UP_SQL = """
CREATE TABLE `afe_job_keyvals` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `job_id` integer NOT NULL,
    INDEX `afe_job_keyvals_job_id` (`job_id`),
    FOREIGN KEY (`job_id`) REFERENCES `afe_jobs` (`id`) ON DELETE NO ACTION,
    `key` varchar(90) NOT NULL,
    INDEX `afe_job_keyvals_key` (`key`),
    `value` varchar(300) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE `tko_job_keyvals` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `job_id` int(10) unsigned NOT NULL,
    INDEX `tko_job_keyvals_job_id` (`job_id`),
    FOREIGN KEY (`job_id`) REFERENCES `tko_jobs` (`job_idx`)
        ON DELETE NO ACTION,
    `key` varchar(90) NOT NULL,
    INDEX `tko_job_keyvals_key` (`key`),
    `value` varchar(300) NOT NULL
) ENGINE=InnoDB;
"""


DOWN_SQL = """
DROP TABLE afe_job_keyvals;
DROP TABLE tko_job_keyvals;
"""
