ADD_FOREIGN_KEYS = """
ALTER TABLE tests MODIFY COLUMN job_idx int(10) unsigned NOT NULL;

DELETE FROM tests WHERE job_idx NOT IN (SELECT job_idx FROM jobs);

ALTER TABLE tests ADD CONSTRAINT tests_to_jobs_ibfk
    FOREIGN KEY (job_idx) REFERENCES jobs (job_idx);
"""

DROP_FOREIGN_KEYS = """
ALTER TABLE tests DROP FOREIGN KEY tests_to_jobs_ibfk;
ALTER TABLE tests MODIFY COLUMN job_idx int(11) NOT NULL;
"""

def migrate_up(mgr):
    mgr.execute_script(ADD_FOREIGN_KEYS)

def migrate_down(mgr):
    mgr.execute_script(DROP_FOREIGN_KEYS)
