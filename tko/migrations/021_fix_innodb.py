UP_SQL = """
ALTER TABLE query_history ENGINE=InnoDB;
ALTER TABLE test_labels ENGINE=InnoDB;
ALTER TABLE test_labels_tests ENGINE=InnoDB;
ALTER TABLE saved_queries ENGINE=InnoDB;
ALTER TABLE embedded_graphing_queries ENGINE=InnoDB;
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    pass
