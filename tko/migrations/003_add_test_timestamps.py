def migrate_up(manager):
    manager.execute_script(ADD_COLUMN_SQL)
    manager.execute_script(ALTER_VIEWS_UP_SQL)


def migrate_down(manager):
    manager.execute_script(DROP_COLUMN_SQL)
    manager.execute_script(ALTER_VIEWS_DOWN_SQL)


ADD_COLUMN_SQL = """\
ALTER TABLE tests ADD COLUMN finished_time datetime NULL;
"""

DROP_COLUMN_SQL = """\
ALTER TABLE tests DROP finished_time;
"""

ALTER_VIEWS_UP_SQL = """\
ALTER VIEW test_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        tests.finished_time AS test_finished_time,
        jobs.tag AS job_tag,
        jobs.label AS job_label,
        jobs.username AS job_username,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        machines.hostname AS machine_hostname,
        machines.machine_group,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel_printable,
        status.word AS status_word
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;

-- perf_view (to make life easier for people trying to mine performance data)
ALTER VIEW perf_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        tests.finished_time AS test_finished_time,
        jobs.tag AS job_tag,
        jobs.label AS job_label,
        jobs.username AS job_username,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        machines.hostname AS machine_hostname,
        machines.machine_group,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel_printable,
        status.word AS status_word,
        iteration_result.iteration,
        iteration_result.attribute AS iteration_key,
        iteration_result.value AS iteration_value
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status
INNER JOIN iteration_result ON iteration_result.test_idx = tests.kernel_idx;
"""


ALTER_VIEWS_DOWN_SQL = """\
ALTER VIEW test_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        jobs.tag AS job_tag,
        jobs.label AS job_label,
        jobs.username AS job_username,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        machines.hostname AS machine_hostname,
        machines.machine_group,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel_printable,
        status.word AS status_word
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;

-- perf_view (to make life easier for people trying to mine performance data)
ALTER VIEW perf_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        jobs.tag AS job_tag,
        jobs.label AS job_label,
        jobs.username AS job_username,
        jobs.queued_time AS job_queued_time,
        jobs.started_time AS job_started_time,
        jobs.finished_time AS job_finished_time,
        machines.hostname AS machine_hostname,
        machines.machine_group,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel_printable,
        status.word AS status_word,
        iteration_result.iteration,
        iteration_result.attribute AS iteration_key,
        iteration_result.value AS iteration_value
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status
INNER JOIN iteration_result ON iteration_result.test_idx = tests.kernel_idx;
"""
