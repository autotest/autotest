UP_SQL = """
ALTER TABLE autotests_dependency_labels ENGINE=InnoDB;
ALTER TABLE jobs_dependency_labels ENGINE=InnoDB;
"""

def migrate_up(manager):
    manager.execute_script(UP_SQL)


def migrate_down(manager):
    pass
