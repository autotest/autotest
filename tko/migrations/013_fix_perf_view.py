def migrate_up(manager):
    manager.execute(ALTER_VIEWS_UP_SQL)


def migrate_down(manager):
    manager.execute(ALTER_VIEWS_DOWN_SQL)


ALTER_VIEWS_UP_SQL = """\
ALTER VIEW perf_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        tests.started_time AS test_started_time,
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
INNER JOIN iteration_result ON iteration_result.test_idx = tests.test_idx;
"""

ALTER_VIEWS_DOWN_SQL = """\
ALTER VIEW perf_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        tests.started_time AS test_started_time,
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
