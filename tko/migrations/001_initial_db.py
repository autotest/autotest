def migrate_up(manager):
    raise Exception('The TKO database is no longer used. Please run migrate.py '
                    'without the -d or --database parameter')


def migrate_down(manager):
    manager.execute_script(DROP_DB_SQL)


DROP_DB_SQL = """\
-- drop all views (since they depend on some or all of the following tables)
DROP VIEW IF EXISTS test_view;
DROP VIEW IF EXISTS perf_view;

DROP TABLE IF EXISTS brrd_sync;
DROP TABLE IF EXISTS iteration_result;
DROP TABLE IF EXISTS test_attributes;
DROP TABLE IF EXISTS tests;
DROP TABLE IF EXISTS patches;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS machines;
DROP TABLE IF EXISTS kernels;
DROP TABLE IF EXISTS status;
"""
