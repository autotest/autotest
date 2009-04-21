ADD_FOREIGN_KEYS = """
ALTER TABLE test_labels_tests MODIFY COLUMN test_id int(10) unsigned NOT NULL;

DELETE FROM test_labels_tests
    WHERE test_id NOT IN (SELECT test_idx FROM tests);

ALTER TABLE test_labels_tests ADD CONSTRAINT tests_labels_tests_ibfk_1
    FOREIGN KEY (testlabel_id) REFERENCES test_labels (id);

ALTER TABLE test_labels_tests ADD CONSTRAINT tests_labels_tests_ibfk_2
    FOREIGN KEY (test_id) REFERENCES tests (test_idx);
"""

DROP_FOREIGN_KEYS = """
ALTER TABLE test_labels_tests DROP FOREIGN KEY tests_labels_tests_ibfk_1;
ALTER TABLE test_labels_tests DROP FOREIGN KEY tests_labels_tests_ibfk_2;
ALTER TABLE test_labels_tests MODIFY COLUMN test_id int(11) NOT NULL;
"""

def migrate_up(mgr):
    mgr.execute_script(ADD_FOREIGN_KEYS)

def migrate_down(mgr):
    mgr.execute_script(DROP_FOREIGN_KEYS)
