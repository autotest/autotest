UP_SQL = """
ALTER TABLE tko_test_labels
ADD CONSTRAINT tko_test_labels_unique
UNIQUE INDEX (name);

INSERT IGNORE INTO tko_test_labels (name, description)
VALUES ('invalidated', '');
"""

DOWN_SQL = """
ALTER TABLE tko_test_labels
DROP INDEX tko_test_labels_unique;
"""
