import common
from autotest_lib.database import db_utils

UP_SQL = """
CREATE INDEX afe_drone_sets_drones_droneset_ibfk
ON afe_drone_sets_drones (droneset_id);

ALTER TABLE afe_drone_sets_drones
DROP KEY afe_drone_sets_drones_unique;

ALTER TABLE afe_drone_sets_drones
ADD CONSTRAINT afe_drone_sets_drones_unique
UNIQUE KEY (drone_id);
"""

# On first migration to 62, this key will be deleted automatically. However, if
# you migrate to 62, then down to 61, then back to 62, this key will remain.
DROP_KEY_SQL = """
ALTER TABLE afe_drone_sets_drones
DROP KEY afe_drone_sets_drones_drone_ibfk;
"""

DOWN_SQL = """
CREATE INDEX afe_drone_sets_drones_drone_ibfk
ON afe_drone_sets_drones (drone_id);

ALTER TABLE afe_drone_sets_drones
DROP KEY afe_drone_sets_drones_unique;

ALTER TABLE afe_drone_sets_drones
ADD CONSTRAINT afe_drone_sets_drones_unique
UNIQUE KEY (droneset_id, drone_id);

ALTER TABLE afe_drone_sets_drones
DROP KEY afe_drone_sets_drones_droneset_ibfk;
"""


def migrate_up(manager):
    query = ('SELECT * FROM afe_drone_sets_drones '
             'GROUP BY drone_id HAVING COUNT(*) > 1')
    rows = manager.execute(query)
    if rows:
        raise Exception('Some drones are associated with more than one drone '
                        'set. Please remove all duplicates before running this '
                        'migration.')
    manager.execute_script(UP_SQL)

    if db_utils.check_index_exists(manager, 'afe_drone_sets_drones',
                                   'afe_drone_sets_drones_drone_ibfk'):
        manager.execute(DROP_KEY_SQL)
