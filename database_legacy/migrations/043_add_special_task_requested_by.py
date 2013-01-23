UP_SQL = """
ALTER TABLE special_tasks ADD requested_by_id integer;

ALTER TABLE special_tasks ADD CONSTRAINT special_tasks_requested_by_id
        FOREIGN KEY (requested_by_id) REFERENCES users (id) ON DELETE NO ACTION;
"""

DOWN_SQL = """
ALTER TABLE special_tasks DROP FOREIGN KEY special_tasks_requested_by_id;
ALTER TABLE special_tasks DROP COLUMN requested_by_id;
"""
