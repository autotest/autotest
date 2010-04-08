UP_SQL = """
ALTER TABLE planner_test_runs
ADD COLUMN invalidated TINYINT(1) DEFAULT FALSE;

ALTER TABLE planner_test_jobs
ADD COLUMN requires_rerun TINYINT(1) DEFAULT FALSE;
"""

DOWN_SQL = """
ALTER TABLE planner_test_jobs
DROP COLUMN requires_rerun;

ALTER TABLE planner_test_runs
DROP COLUMN invalidated;
"""
