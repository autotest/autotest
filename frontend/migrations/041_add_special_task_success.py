UP_SQL = """
ALTER TABLE special_tasks
ADD COLUMN success TINYINT(1)
NOT NULL DEFAULT 0;

UPDATE special_tasks
SET success = 1
WHERE is_complete = 1;
"""

DOWN_SQL = """
ALTER TABLE special_tasks
DROP COLUMN success;
"""
