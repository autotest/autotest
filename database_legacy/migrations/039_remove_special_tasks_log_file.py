UP_SQL = 'ALTER TABLE special_tasks DROP COLUMN log_file'

DOWN_SQL = """
ALTER TABLE special_tasks ADD COLUMN log_file VARCHAR(45) NOT NULL DEFAULT ''
"""
