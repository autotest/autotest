CREATE VIEW tko_test_view AS
        SELECT  tko_tests.test_idx AS test_idx,
                tko_tests.job_idx AS job_idx,
                tko_tests.test AS test,
                tko_tests.subdir AS subdir,
                tko_tests.kernel_idx AS kernel_idx,
                tko_tests.status AS status,
                tko_tests.reason AS reason,
                tko_tests.machine_idx AS machine_idx,
                tko_tests.started_time AS test_started_time,
                tko_tests.finished_time AS test_finished_time,
                tko_jobs.tag AS job_tag,
                tko_jobs.label AS job_label,
                tko_jobs.username AS job_username,
                tko_jobs.queued_time AS job_queued_time,
                tko_jobs.started_time AS job_started_time,
                tko_jobs.finished_time AS job_finished_time,
                tko_machines.hostname AS machine_hostname,
                tko_machines.machine_group AS machine_group,
                tko_machines.owner AS machine_owner,
                tko_kernels.kernel_hash AS kernel_hash,
                tko_kernels.base AS kernel_base,
                tko_kernels.printable AS kernel_printable,
                tko_status.word AS status_word
        FROM
                tko_tests JOIN tko_jobs ON tko_jobs.job_idx = tko_tests.job_idx
                JOIN tko_machines ON tko_machines.machine_idx = tko_jobs.machine_idx
                JOIN tko_kernels ON tko_kernels.kernel_idx = tko_tests.kernel_idx
                JOIN tko_status ON tko_status.status_idx = tko_tests.status;

