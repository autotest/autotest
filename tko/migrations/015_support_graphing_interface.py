def migrate_up(manager):
    manager.execute(CREATE_QUERIES_TABLE)
    manager.execute(CREATE_TEST_VIEW_OUTER_JOINS)
    manager.execute(CREATE_PERF_VIEW_2)

def migrate_down(manager):
    manager.execute(DROP_QUERIES_TABLE)
    manager.execute(DROP_TEST_VIEW_OUTER_JOINS)
    manager.execute(DROP_PERF_VIEW_2)


CREATE_QUERIES_TABLE = """\
CREATE TABLE embedded_graphing_queries (
    id INT NOT NULL AUTO_INCREMENT,
    url_token TEXT NOT NULL,
    graph_type VARCHAR(16) NOT NULL,
    params TEXT NOT NULL,
    last_accessed DATETIME NOT NULL,
    PRIMARY KEY(id),
    INDEX (url_token(128)))
"""

DROP_QUERIES_TABLE = """\
DROP TABLE IF EXISTS embedded_graphing_queries
"""

CREATE_TEST_VIEW_OUTER_JOINS = """\
CREATE VIEW test_view_outer_joins AS
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
LEFT OUTER JOIN jobs ON jobs.job_idx = tests.job_idx
LEFT OUTER JOIN machines ON machines.machine_idx = jobs.machine_idx
LEFT OUTER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
LEFT OUTER JOIN status ON status.status_idx = tests.status;
"""

DROP_TEST_VIEW_OUTER_JOINS = """\
DROP VIEW IF EXISTS test_view_outer_joins
"""

CREATE_PERF_VIEW_2 = """\
CREATE VIEW perf_view_2 AS
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
        status.word AS status,
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

DROP_PERF_VIEW_2 = """\
DROP VIEW IF EXISTS perf_view_2
"""
