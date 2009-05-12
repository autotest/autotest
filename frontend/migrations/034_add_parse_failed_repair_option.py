UP_SQL = """
ALTER TABLE jobs ADD COLUMN parse_failed_repair bool NOT NULL DEFAULT TRUE;
"""

DOWN_SQL = """
ALTER TABLE jobs DROP COLUMN parse_failed_repair;
"""
