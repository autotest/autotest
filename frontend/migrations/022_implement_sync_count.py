DOWN_SQL = """
ALTER TABLE jobs ADD COLUMN synchronizing tinyint(1) default NULL;
ALTER TABLE autotests ADD COLUMN synch_type smallint(6) NOT NULL;
UPDATE autotests SET synch_type = 1;
UPDATE autotests SET synch_type = 2 WHERE sync_count > 1;
ALTER TABLE jobs ADD COLUMN synch_type int(11) default NULL;
UPDATE jobs SET synch_type = 1;
UPDATE jobs SET synch_type = 2 WHERE synch_count > 1;
ALTER TABLE host_queue_entries DROP COLUMN `execution_subdir`;
"""

def migrate_up(manager):
    # add execution_subdir field
    manager.execute("""ALTER TABLE host_queue_entries ADD COLUMN
                       `execution_subdir` varchar(255) NOT NULL""")

    # fill in execution_subdir field for running/complete entries
    rows = manager.execute("""
        SELECT jobs.id, jobs.synch_type, COUNT(1) FROM jobs
        INNER JOIN host_queue_entries AS hqe ON jobs.id = hqe.job_id
        GROUP BY jobs.id""")
    job_hqe_count = dict((row[0], row[2]) for row in rows)
    synch_jobs = set(row[0] for row in rows if row[1] == 2)
    hqes = manager.execute("""
        SELECT hqe.id, hqe.job_id, hqe.status, hqe.complete, hosts.hostname
        FROM host_queue_entries AS hqe
        INNER JOIN hosts ON hqe.host_id = hosts.id
        WHERE hqe.status IN ('Starting', 'Running') OR complete""")
    for id, job_id, status, complete, hostname in hqes:
        if job_id in synch_jobs or job_hqe_count[job_id] == 1:
            execution_subdir = ''
        else:
            execution_subdir = hostname
        manager.execute(
            'UPDATE host_queue_entries SET execution_subdir = %s WHERE id = %s',
            execution_subdir, id)

    # ensure synch_type information doesn't get lost if we need to migrate down
    manager.execute('UPDATE jobs SET synch_count = 1 WHERE synch_type = 1')
    manager.execute('UPDATE jobs SET synch_count = 2 '
                    'WHERE synch_type = 2 AND synch_count = 1')
    # drop the old synch_type fields
    manager.execute('ALTER TABLE jobs DROP COLUMN synch_type')
    manager.execute('ALTER TABLE autotests DROP COLUMN synch_type')
    # drop deprecated synchronizing field
    manager.execute('ALTER TABLE jobs DROP COLUMN synchronizing')


def migrate_down(manager):
    manager.execute_script(DOWN_SQL)
