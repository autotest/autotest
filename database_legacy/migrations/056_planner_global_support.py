UP_SQL = """
CREATE TABLE planner_test_configs_skipped_hosts (
  testconfig_id INT NOT NULL,
  host_id INT NOT NULL,
  PRIMARY KEY (testconfig_id, host_id)
) ENGINE = InnoDB;

ALTER TABLE planner_test_configs_skipped_hosts
ADD CONSTRAINT planner_test_configs_skipped_hosts_testconfig_ibfk
FOREIGN KEY (testconfig_id) REFERENCES planner_test_configs (id);

ALTER TABLE planner_test_configs_skipped_hosts
ADD CONSTRAINT planner_test_configs_skipped_hosts_host_ibfk
FOREIGN KEY (host_id) REFERENCES afe_hosts (id);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS planner_test_configs_skipped_hosts;
"""
