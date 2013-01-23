UP_SQL = """
CREATE TABLE afe_drones (
  id INT AUTO_INCREMENT NOT NULL PRIMARY KEY,
  hostname VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

ALTER TABLE afe_drones
ADD CONSTRAINT afe_drones_unique
UNIQUE KEY (hostname);


CREATE TABLE afe_drone_sets (
  id INT AUTO_INCREMENT NOT NULL PRIMARY KEY,
  name VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

ALTER TABLE afe_drone_sets
ADD CONSTRAINT afe_drone_sets_unique
UNIQUE KEY (name);


CREATE TABLE afe_drone_sets_drones (
  id INT AUTO_INCREMENT NOT NULL PRIMARY KEY,
  droneset_id INT NOT NULL,
  drone_id INT NOT NULL
) ENGINE=InnoDB;

ALTER TABLE afe_drone_sets_drones
ADD CONSTRAINT afe_drone_sets_drones_droneset_ibfk
FOREIGN KEY (droneset_id) REFERENCES afe_drone_sets (id);

ALTER TABLE afe_drone_sets_drones
ADD CONSTRAINT afe_drone_sets_drones_drone_ibfk
FOREIGN KEY (drone_id) REFERENCES afe_drones (id);

ALTER TABLE afe_drone_sets_drones
ADD CONSTRAINT afe_drone_sets_drones_unique
UNIQUE KEY (droneset_id, drone_id);


ALTER TABLE afe_jobs
ADD COLUMN drone_set_id INT;

ALTER TABLE afe_jobs
ADD CONSTRAINT afe_jobs_drone_set_ibfk
FOREIGN KEY (drone_set_id) REFERENCES afe_drone_sets (id);


ALTER TABLE afe_users
ADD COLUMN drone_set_id INT;

ALTER TABLE afe_users
ADD CONSTRAINT afe_users_drone_set_ibfk
FOREIGN KEY (drone_set_id) REFERENCES afe_drone_sets (id);


UPDATE afe_special_tasks SET requested_by_id = (
  SELECT id FROM afe_users WHERE login = 'autotest_system')
WHERE requested_by_id IS NULL;

ALTER TABLE afe_special_tasks
MODIFY COLUMN requested_by_id INT NOT NULL;
"""


DOWN_SQL = """
ALTER TABLE afe_special_tasks
MODIFY COLUMN requested_by_id INT DEFAULT NULL;

ALTER TABLE afe_users
DROP FOREIGN KEY afe_users_drone_set_ibfk;

ALTER TABLE afe_users
DROP COLUMN drone_set_id;

ALTER TABLE afe_jobs
DROP FOREIGN KEY afe_jobs_drone_set_ibfk;

ALTER TABLE afe_jobs
DROP COLUMN drone_set_id;

DROP TABLE IF EXISTS afe_drone_sets_drones;
DROP TABLE IF EXISTS afe_drone_sets;
DROP TABLE IF EXISTS afe_drones;
"""
