import common
from autotest_lib.database import db_utils


RECREATE_VIEWS_UP = """
CREATE VIEW tko_test_view AS
SELECT  tko_tests.test_idx,
        tko_tests.job_idx,
        tko_tests.test,
        tko_tests.subdir,
        tko_tests.kernel_idx,
        tko_tests.status,
        tko_tests.reason,
        tko_tests.machine_idx,
        tko_tests.started_time AS test_started_time,
        tko_tests.finished_time AS test_finished_time,
        tko_jobs.tag AS job_tag,
        tko_jobs.label AS job_label,
        tko_jobs.username AS job_username,
        tko_jobs.queued_time AS job_queued_time,
        tko_jobs.started_time AS job_started_time,
        tko_jobs.finished_time AS job_finished_time,
        tko_machines.hostname AS machine_hostname,
        tko_machines.machine_group,
        tko_machines.owner AS machine_owner,
        tko_kernels.kernel_hash,
        tko_kernels.base AS kernel_base,
        tko_kernels.printable AS kernel_printable,
        tko_status.word AS status_word
FROM tko_tests
INNER JOIN tko_jobs ON tko_jobs.job_idx = tko_tests.job_idx
INNER JOIN tko_machines ON tko_machines.machine_idx = tko_jobs.machine_idx
INNER JOIN tko_kernels ON tko_kernels.kernel_idx = tko_tests.kernel_idx
INNER JOIN tko_status ON tko_status.status_idx = tko_tests.status;


CREATE VIEW tko_perf_view AS
SELECT  tko_tests.test_idx,
        tko_tests.job_idx,
        tko_tests.test,
        tko_tests.subdir,
        tko_tests.kernel_idx,
        tko_tests.status,
        tko_tests.reason,
        tko_tests.machine_idx,
        tko_tests.started_time AS test_started_time,
        tko_tests.finished_time AS test_finished_time,
        tko_jobs.tag AS job_tag,
        tko_jobs.label AS job_label,
        tko_jobs.username AS job_username,
        tko_jobs.queued_time AS job_queued_time,
        tko_jobs.started_time AS job_started_time,
        tko_jobs.finished_time AS job_finished_time,
        tko_machines.hostname AS machine_hostname,
        tko_machines.machine_group,
        tko_machines.owner AS machine_owner,
        tko_kernels.kernel_hash,
        tko_kernels.base AS kernel_base,
        tko_kernels.printable AS kernel_printable,
        tko_status.word AS status_word,
        tko_iteration_result.iteration,
        tko_iteration_result.attribute AS iteration_key,
        tko_iteration_result.value AS iteration_value
FROM tko_tests
INNER JOIN tko_jobs ON tko_jobs.job_idx = tko_tests.job_idx
INNER JOIN tko_machines ON tko_machines.machine_idx = tko_jobs.machine_idx
INNER JOIN tko_kernels ON tko_kernels.kernel_idx = tko_tests.kernel_idx
INNER JOIN tko_status ON tko_status.status_idx = tko_tests.status
INNER JOIN tko_iteration_result ON
        tko_iteration_result.test_idx = tko_tests.test_idx;


CREATE VIEW tko_test_view_2 AS
SELECT  tko_tests.test_idx,
        tko_tests.job_idx,
        tko_tests.test AS test_name,
        tko_tests.subdir,
        tko_tests.kernel_idx,
        tko_tests.status AS status_idx,
        tko_tests.reason,
        tko_tests.machine_idx,
        tko_tests.started_time AS test_started_time,
        tko_tests.finished_time AS test_finished_time,
        tko_jobs.tag AS job_tag,
        tko_jobs.label AS job_name,
        tko_jobs.username AS job_owner,
        tko_jobs.queued_time AS job_queued_time,
        tko_jobs.started_time AS job_started_time,
        tko_jobs.finished_time AS job_finished_time,
        tko_jobs.afe_job_id AS afe_job_id,
        tko_machines.hostname AS hostname,
        tko_machines.machine_group AS platform,
        tko_machines.owner AS machine_owner,
        tko_kernels.kernel_hash,
        tko_kernels.base AS kernel_base,
        tko_kernels.printable AS kernel,
        tko_status.word AS status
FROM tko_tests
INNER JOIN tko_jobs ON tko_jobs.job_idx = tko_tests.job_idx
INNER JOIN tko_machines ON tko_machines.machine_idx = tko_jobs.machine_idx
INNER JOIN tko_kernels ON tko_kernels.kernel_idx = tko_tests.kernel_idx
INNER JOIN tko_status ON tko_status.status_idx = tko_tests.status;


CREATE VIEW tko_test_view_outer_joins AS
SELECT  tko_tests.test_idx,
        tko_tests.job_idx,
        tko_tests.test AS test_name,
        tko_tests.subdir,
        tko_tests.kernel_idx,
        tko_tests.status AS status_idx,
        tko_tests.reason,
        tko_tests.machine_idx,
        tko_tests.started_time AS test_started_time,
        tko_tests.finished_time AS test_finished_time,
        tko_jobs.tag AS job_tag,
        tko_jobs.label AS job_name,
        tko_jobs.username AS job_owner,
        tko_jobs.queued_time AS job_queued_time,
        tko_jobs.started_time AS job_started_time,
        tko_jobs.finished_time AS job_finished_time,
        tko_machines.hostname AS hostname,
        tko_machines.machine_group AS platform,
        tko_machines.owner AS machine_owner,
        tko_kernels.kernel_hash,
        tko_kernels.base AS kernel_base,
        tko_kernels.printable AS kernel,
        tko_status.word AS status
FROM tko_tests
LEFT OUTER JOIN tko_jobs ON tko_jobs.job_idx = tko_tests.job_idx
LEFT OUTER JOIN tko_machines ON tko_machines.machine_idx = tko_jobs.machine_idx
LEFT OUTER JOIN tko_kernels ON tko_kernels.kernel_idx = tko_tests.kernel_idx
LEFT OUTER JOIN tko_status ON tko_status.status_idx = tko_tests.status;


CREATE VIEW tko_perf_view_2 AS
SELECT  tko_tests.test_idx,
        tko_tests.job_idx,
        tko_tests.test AS test_name,
        tko_tests.subdir,
        tko_tests.kernel_idx,
        tko_tests.status AS status_idx,
        tko_tests.reason,
        tko_tests.machine_idx,
        tko_tests.started_time AS test_started_time,
        tko_tests.finished_time AS test_finished_time,
        tko_jobs.tag AS job_tag,
        tko_jobs.label AS job_name,
        tko_jobs.username AS job_owner,
        tko_jobs.queued_time AS job_queued_time,
        tko_jobs.started_time AS job_started_time,
        tko_jobs.finished_time AS job_finished_time,
        tko_machines.hostname AS hostname,
        tko_machines.machine_group AS platform,
        tko_machines.owner AS machine_owner,
        tko_kernels.kernel_hash,
        tko_kernels.base AS kernel_base,
        tko_kernels.printable AS kernel,
        tko_status.word AS status,
        tko_iteration_result.iteration,
        tko_iteration_result.attribute AS iteration_key,
        tko_iteration_result.value AS iteration_value
FROM tko_tests
LEFT OUTER JOIN tko_jobs ON tko_jobs.job_idx = tko_tests.job_idx
LEFT OUTER JOIN tko_machines ON tko_machines.machine_idx = tko_jobs.machine_idx
LEFT OUTER JOIN tko_kernels ON tko_kernels.kernel_idx = tko_tests.kernel_idx
LEFT OUTER JOIN tko_status ON tko_status.status_idx = tko_tests.status
LEFT OUTER JOIN tko_iteration_result ON
        tko_iteration_result.test_idx = tko_tests.test_idx;
"""


RECREATE_VIEWS_DOWN = """
CREATE VIEW test_view AS
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
        status.word AS status_word
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;


CREATE VIEW perf_view AS
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


CREATE VIEW test_view_2 AS
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
LEFT OUTER JOIN jobs ON jobs.job_idx = tests.job_idx
LEFT OUTER JOIN machines ON machines.machine_idx = jobs.machine_idx
LEFT OUTER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
LEFT OUTER JOIN status ON status.status_idx = tests.status
LEFT OUTER JOIN iteration_result ON iteration_result.test_idx = tests.test_idx;
"""


ORIG_NAMES = (
        'embedded_graphing_queries',
        'iteration_attributes',
        'iteration_result',
        'jobs',
        'kernels',
        'machines',
        'patches',
        'query_history',
        'saved_queries',
        'status',
        'test_attributes',
        'test_labels',
        'test_labels_tests',
        'tests',
        )

RENAMES_UP = dict((name, 'tko_' + name) for name in ORIG_NAMES)
VIEWS_TO_DROP_UP = (
        'test_view',
        'test_view_2',
        'test_view_outer_joins',
        'perf_view',
        'perf_view_2',
        )

RENAMES_DOWN = dict((value, key) for key, value in RENAMES_UP.iteritems())
VIEWS_TO_DROP_DOWN = ['tko_' + view for view in VIEWS_TO_DROP_UP]


def migrate_up(manager):
    db_utils.drop_views(manager, VIEWS_TO_DROP_UP)
    db_utils.rename(manager, RENAMES_UP)
    manager.execute_script(RECREATE_VIEWS_UP)


def migrate_down(manager):
    db_utils.drop_views(manager, VIEWS_TO_DROP_DOWN)
    db_utils.rename(manager, RENAMES_DOWN)
    manager.execute_script(RECREATE_VIEWS_DOWN)
