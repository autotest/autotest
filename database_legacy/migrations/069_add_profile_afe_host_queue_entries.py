UP_SQL = """
ALTER TABLE afe_host_queue_entries ADD COLUMN profile VARCHAR(255) AFTER host_id;
"""

DOWN_SQL = """
ALTER TABLE afe_host_queue_entries DROP COLUMN profile;
"""
