UP_SQL = """
ALTER TABLE hosts
ADD CONSTRAINT hosts_locked_by_fk FOREIGN KEY
(locked_by_id) REFERENCES users(id)
ON DELETE NO ACTION;

ALTER TABLE host_queue_entries
ADD CONSTRAINT host_queue_entries_job_id_fk FOREIGN KEY
(job_id) REFERENCES jobs(id)
ON DELETE NO ACTION;

INSERT INTO hosts (hostname, invalid, protection, dirty)
VALUES ('__missing_host__', 1, 0, 1);

UPDATE host_queue_entries AS hqe
    LEFT OUTER JOIN hosts ON (hqe.host_id = hosts.id)
SET hqe.host_id = (SELECT id FROM hosts WHERE hostname = '__missing_host__')
WHERE hqe.host_id IS NOT NULL AND hosts.id IS NULL;

ALTER TABLE host_queue_entries
ADD CONSTRAINT host_queue_entries_host_id_fk FOREIGN KEY
(host_id) REFERENCES hosts(id)
ON DELETE NO ACTION;

ALTER TABLE host_queue_entries
ADD CONSTRAINT host_queue_entries_meta_host_fk FOREIGN KEY
(meta_host) REFERENCES labels(id)
ON DELETE NO ACTION;

ALTER TABLE aborted_host_queue_entries
ADD CONSTRAINT aborted_host_queue_entries_queue_entry_id_fk FOREIGN KEY
(queue_entry_id) REFERENCES host_queue_entries(id)
ON DELETE NO ACTION;

ALTER TABLE aborted_host_queue_entries
ADD CONSTRAINT aborted_host_queue_entries_aborted_by_id_fk FOREIGN KEY
(aborted_by_id) REFERENCES users(id)
ON DELETE NO ACTION;

ALTER TABLE recurring_run
ADD CONSTRAINT recurring_run_job_id_fk FOREIGN KEY
(job_id) REFERENCES jobs(id)
ON DELETE NO ACTION;

ALTER TABLE recurring_run
ADD CONSTRAINT recurring_run_owner_id_fk FOREIGN KEY
(owner_id) REFERENCES users(id)
ON DELETE NO ACTION;
"""

DOWN_SQL = """
ALTER TABLE hosts
DROP FOREIGN KEY hosts_locked_by_fk;

ALTER TABLE host_queue_entries
DROP FOREIGN KEY host_queue_entries_job_id_fk;

ALTER TABLE host_queue_entries
DROP FOREIGN KEY host_queue_entries_host_id_fk;

ALTER TABLE host_queue_entries
DROP FOREIGN KEY host_queue_entries_meta_host_fk;

ALTER TABLE aborted_host_queue_entries
DROP FOREIGN KEY aborted_host_queue_entries_queue_entry_id_fk;

ALTER TABLE aborted_host_queue_entries
DROP FOREIGN KEY aborted_host_queue_entries_aborted_by_id_fk;

ALTER TABLE recurring_run
DROP FOREIGN KEY recurring_run_job_id_fk;

ALTER TABLE recurring_run
DROP FOREIGN KEY recurring_run_owner_id_fk;
"""
