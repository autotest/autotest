UP_SQL = """
ALTER TABLE host_queue_entries ADD COLUMN started_on datetime NULL;
ALTER TABLE jobs ADD COLUMN max_runtime_hrs integer NOT NULL;
-- conservative value for existing jobs, to make sure they don't get
-- unexpectedly timed out.
UPDATE jobs SET max_runtime_hrs = timeout;
"""

DOWN_SQL = """
ALTER TABLE jobs DROP COLUMN max_runtime_hrs;
ALTER TABLE host_queue_entries DROP COLUMN started_on;
"""
