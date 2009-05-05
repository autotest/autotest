UP_SQL = """
UPDATE saved_queries
SET url_token = REPLACE(url_token, 'view=Metrics+Plot', 'view=metrics_plot');
"""

def migrate_up(manager):
    manager.execute(UP_SQL)

def migrate_down(manager):
    pass
