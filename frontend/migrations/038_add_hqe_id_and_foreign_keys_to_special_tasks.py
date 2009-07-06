UP_SQL = """
UPDATE special_tasks
SET task = 'Verify'
WHERE task = 'Reverify';

ALTER TABLE special_tasks
ADD COLUMN time_started DATETIME;

ALTER TABLE special_tasks
ADD COLUMN log_file VARCHAR(45) NOT NULL DEFAULT '';

ALTER TABLE special_tasks
ADD COLUMN queue_entry_id INT;

ALTER TABLE special_tasks
ADD CONSTRAINT special_tasks_to_hosts_ibfk FOREIGN KEY
(host_id) REFERENCES hosts(id);

ALTER TABLE special_tasks
ADD CONSTRAINT special_tasks_to_host_queue_entries_ibfk
FOREIGN KEY special_tasks_host_queue_entry_id
(queue_entry_id) REFERENCES host_queue_entries(id);
"""

DOWN_SQL = """
ALTER TABLE special_tasks DROP FOREIGN KEY
    special_tasks_to_host_queue_entries_ibfk;
ALTER TABLE special_tasks DROP FOREIGN KEY special_tasks_to_hosts_ibfk;
ALTER TABLE special_tasks DROP COLUMN queue_entry_id;
ALTER TABLE special_tasks DROP COLUMN log_file;
ALTER TABLE special_tasks DROP COLUMN time_started;
"""
