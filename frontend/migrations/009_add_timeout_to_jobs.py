from autotest_lib.client.common_lib import global_config

def migrate_up(manager):
    # Add the column with a default first, and then drop the default.
    # We cannot add the column, populate the values, and then specify NOT NULL
    # because a record added while this is executing could enter a null value
    # into the table before NOT NULL is specified.
    manager.execute(ADD_COLUMN)
    manager.execute(DROP_DEFAULT)

def migrate_down(manager):
    manager.execute(DROP_COLUMN)

job_timeout_default = global_config.global_config.get_config_value(
    'AUTOTEST_WEB', 'job_timeout_default')
ADD_COLUMN = ('ALTER TABLE jobs ADD COLUMN timeout INT NOT NULL DEFAULT %s'
              % job_timeout_default)
DROP_DEFAULT = 'ALTER TABLE jobs ALTER COLUMN timeout DROP DEFAULT'
DROP_COLUMN = 'ALTER TABLE jobs DROP COLUMN timeout'
