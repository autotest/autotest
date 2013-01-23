UP_SQL = """
CREATE TABLE special_tasks (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  host_id INT NOT NULL REFERENCES hosts(id),
  task VARCHAR(64) NOT NULL,
  time_requested DATETIME NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT FALSE,
  is_complete TINYINT(1) NOT NULL DEFAULT FALSE,
  INDEX special_tasks_host_id (host_id)
) ENGINE=innodb;
"""

DOWN_SQL = """
DROP TABLE special_tasks;
"""
