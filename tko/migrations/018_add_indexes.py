def migrate_up(manager):
    manager.execute_script(CREATE_INDICES)


def migrate_down(manager):
    manager.execute_script(DROP_INDICES)


CREATE_INDICES = """
CREATE INDEX job_idx ON tests (job_idx);
CREATE INDEX reason ON tests (reason);
CREATE INDEX test ON tests (test);
CREATE INDEX subdir ON tests (subdir);
CREATE INDEX printable ON kernels (printable);
CREATE INDEX word ON status (word);
CREATE INDEX attribute ON test_attributes (attribute);
CREATE INDEX value ON test_attributes (value);
CREATE INDEX attribute ON iteration_result (attribute);
CREATE INDEX value ON iteration_result (value);
"""


DROP_INDICES = """
DROP INDEX job_idx ON tests;
DROP INDEX reason ON tests;
DROP INDEX test ON tests;
DROP INDEX subdir ON tests;
DROP INDEX printable ON kernels;
DROP INDEX word ON status;
DROP INDEX attribute ON test_attributes;
DROP INDEX value ON test_attributes;
DROP INDEX attribute ON iteration_result;
DROP INDEX value ON iteration_result;
"""
