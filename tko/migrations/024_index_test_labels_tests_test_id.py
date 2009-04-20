def migrate_up(manager):
    manager.execute('CREATE INDEX test_labels_tests_test_id '
                    'ON test_labels_tests (test_id)')


def migrate_down(manager):
    manager.execute('DROP INDEX test_labels_tests_test_id ON test_labels_tests')
