UP_SQL = """
CREATE INDEX afe_drone_sets_drones_droneset_ibfk
ON afe_drone_sets_drones (droneset_id);

ALTER TABLE afe_drone_sets_drones
DROP KEY afe_drone_sets_drones_unique;

ALTER TABLE afe_drone_sets_drones
ADD CONSTRAINT afe_drone_sets_drones_unique
UNIQUE KEY (drone_id);

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
