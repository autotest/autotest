UP_SQL = """
ALTER TABLE jobs
ADD COLUMN afe_job_id INT DEFAULT NULL;

UPDATE jobs
SET afe_job_id = SUBSTRING_INDEX(tag, '-', 1)
WHERE tag REGEXP '^[0-9]+-.+/.+$';

CREATE INDEX afe_job_id
ON jobs(afe_job_id);

ALTER VIEW test_view_2 AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test AS test_name,
        tests.subdir,
        tests.kernel_idx,
        tests.status AS status_idx,
        tests.reason,
        tests.machine_idx,
        tests.started_time AS test_started_time,
        tests.finished_time AS test_finished_time,
        jobs.tag AS job_tag,
        jobs.label AS job_name,
        jobs.username AS job_owner,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        jobs.afe_job_id AS afe_job_id,
        machines.hostname AS hostname,
        machines.machine_group AS platform,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel,
        status.word AS status
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;
"""

DOWN_SQL = """
ALTER VIEW test_view_2 AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test AS test_name,
        tests.subdir,
        tests.kernel_idx,
        tests.status AS status_idx,
        tests.reason,
        tests.machine_idx,
        tests.started_time AS test_started_time,
        tests.finished_time AS test_finished_time,
        jobs.tag AS job_tag,
        jobs.label AS job_name,
        jobs.username AS job_owner,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        machines.hostname AS hostname,
        machines.machine_group AS platform,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel,
        status.word AS status
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;

ALTER TABLE jobs
DROP COLUMN afe_job_id;
"""
