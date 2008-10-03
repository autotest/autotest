import os

required_tables = ('machines', 'jobs', 'patches', 'tests', 'test_attributes',
                   'iteration_result')

def migrate_up(manager):
    rows = manager.execute("SHOW TABLES")
    tables = [row[0] for row in rows]
    db_initialized = True
    for table in required_tables:
        if table not in tables:
            db_initialized = False
            break
    if not db_initialized:
        if not manager.force:
            response = raw_input(
                'Your autotest_web database does not appear to be '
                'initialized.  Do you want to recreate it (this will '
                'result in loss of any existing data) (yes/No)? ')
            if response != 'yes':
                raise Exception('User has chosen to abort migration')

        manager.execute_script(CREATE_DB_SQL)

    manager.create_migrate_table()


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


CREATE_DB_SQL = DROP_DB_SQL + """\
-- status key
CREATE TABLE status (
status_idx int(10) unsigned NOT NULL auto_increment PRIMARY KEY ,               -- numerical status
word VARCHAR(10)                        -- status word
) TYPE=InnoDB;

-- kernel versions
CREATE TABLE kernels (
kernel_idx int(10) unsigned NOT NULL auto_increment PRIMARY KEY,
kernel_hash VARCHAR(35),                -- Hash of base + all patches
base VARCHAR(30),                       -- Base version without patches
printable VARCHAR(100)                  -- Full version with patches
) TYPE=InnoDB;

-- machines/hosts table
CREATE TABLE machines (
machine_idx int(10) unsigned NOT NULL auto_increment PRIMARY KEY,
hostname VARCHAR(100) unique KEY,       -- hostname
machine_group VARCHAR(80),              -- group name
owner VARCHAR(80)                       -- owner name
) TYPE=InnoDB;

-- main jobs table
CREATE TABLE jobs (
job_idx int(10) unsigned NOT NULL auto_increment PRIMARY KEY,   -- index number
tag VARCHAR(100) unique KEY,            -- job key
label VARCHAR(100),                     -- job label assigned by user
KEY (label),
username VARCHAR(80),                   -- user name
KEY (username),
machine_idx INT(10) unsigned NOT NULL,  -- reference to machine table
KEY (machine_idx),
FOREIGN KEY (machine_idx) REFERENCES machines(machine_idx) ON DELETE CASCADE
) TYPE=InnoDB;

-- One entry per patch used, anywhere
CREATE TABLE patches (
kernel_idx INT(10) unsigned NOT NULL,   -- index number
name VARCHAR(80),                       -- short name
url VARCHAR(300),                       -- full URL
hash VARCHAR(35),
KEY (kernel_idx),
FOREIGN KEY (kernel_idx) REFERENCES kernels(kernel_idx) ON DELETE CASCADE
) TYPE=InnoDB;

-- test functional results
CREATE TABLE tests (
test_idx int(10) unsigned NOT NULL auto_increment PRIMARY KEY,  -- index number
job_idx INTEGER,                        -- ref to job table
test VARCHAR(30),                       -- name of test
subdir VARCHAR(60),                     -- subdirectory name
kernel_idx INT(10) unsigned NOT NULL,   -- kernel test was AGAINST
KEY (kernel_idx),
FOREIGN KEY (kernel_idx) REFERENCES kernels(kernel_idx) ON DELETE CASCADE,
status int(10) unsigned NOT NULL,       -- test status
KEY (status),
FOREIGN KEY (status) REFERENCES status(status_idx) ON DELETE CASCADE,
reason VARCHAR(100),                    -- reason for test status
machine_idx INT(10) unsigned NOT NULL,  -- reference to machine table
KEY (machine_idx),
FOREIGN KEY (machine_idx) REFERENCES machines(machine_idx) ON DELETE CASCADE,
invalid BOOL NOT NULL
) TYPE=InnoDB;

-- test attributes (key value pairs at a test level)
CREATE TABLE test_attributes (
test_idx int(10) unsigned NOT NULL,     -- ref to test table
FOREIGN KEY (test_idx) REFERENCES tests(test_idx) ON DELETE CASCADE,
attribute VARCHAR(30),                  -- attribute name (e.g. 'version')
value VARCHAR(100),                     -- attribute value
KEY `test_idx` (`test_idx`)
) TYPE=InnoDB;

-- test performance results
CREATE TABLE iteration_result(
test_idx int(10) unsigned NOT NULL,     -- ref to test table
FOREIGN KEY (test_idx) REFERENCES tests(test_idx) ON DELETE CASCADE,
iteration INTEGER,                      -- integer
attribute VARCHAR(30),                  -- attribute name (e.g. 'throughput')
value FLOAT,                            -- attribute value (eg 700.1)
KEY `test_idx` (`test_idx`)
) TYPE=InnoDB;

-- BRRD syncronization
CREATE TABLE brrd_sync (
test_idx int(10) unsigned NOT NULL,     -- ref to test table
FOREIGN KEY (test_idx) REFERENCES tests(test_idx) ON DELETE CASCADE
) TYPE=InnoDB;

-- test_view (to make life easier for people trying to mine data)
CREATE VIEW test_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        jobs.tag AS job_tag,
        jobs.label AS job_label,
        jobs.username AS job_username,
        machines.hostname AS machine_hostname,
        machines.machine_group,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel_printable,
        status.word AS status_word
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status;

-- perf_view (to make life easier for people trying to mine performance data)
CREATE VIEW perf_view AS
SELECT  tests.test_idx,
        tests.job_idx,
        tests.test,
        tests.subdir,
        tests.kernel_idx,
        tests.status,
        tests.reason,
        tests.machine_idx,
        jobs.tag AS job_tag,
        jobs.label AS job_label,
        jobs.username AS job_username,
        machines.hostname AS machine_hostname,
        machines.machine_group,
        machines.owner AS machine_owner,
        kernels.kernel_hash,
        kernels.base AS kernel_base,
        kernels.printable AS kernel_printable,
        status.word AS status_word,
        iteration_result.iteration,
        iteration_result.attribute AS iteration_key,
        iteration_result.value AS iteration_value
FROM tests
INNER JOIN jobs ON jobs.job_idx = tests.job_idx
INNER JOIN machines ON machines.machine_idx = jobs.machine_idx
INNER JOIN kernels ON kernels.kernel_idx = tests.kernel_idx
INNER JOIN status ON status.status_idx = tests.status
INNER JOIN iteration_result ON iteration_result.test_idx = tests.kernel_idx;

INSERT INTO status (word)
VALUES ('NOSTATUS'), ('ERROR'), ('ABORT'), ('FAIL'), ('WARN'), ('GOOD'), ('ALERT');
"""
