UP_SQL = """
CREATE TABLE planner_additional_parameters (
  id INT PRIMARY KEY AUTO_INCREMENT,
  plan_id INT NOT NULL,
  hostname_regex VARCHAR(255) NOT NULL,
  param_type VARCHAR(32) NOT NULL,
  application_order INT NOT NULL
) ENGINE = InnoDB;

ALTER TABLE planner_additional_parameters
ADD CONSTRAINT planner_additional_parameters_plan_ibfk
FOREIGN KEY (plan_id) REFERENCES planner_plans (id);

ALTER TABLE planner_additional_parameters
ADD CONSTRAINT planner_additional_parameters_unique
UNIQUE KEY (plan_id, hostname_regex, param_type);


CREATE TABLE planner_additional_parameter_values (
  id INT PRIMARY KEY AUTO_INCREMENT,
  additional_parameter_id INT NOT NULL,
  `key` VARCHAR(255) NOT NULL,
  value VARCHAR(255) NOT NULL
) ENGINE = InnoDB;

ALTER TABLE planner_additional_parameter_values
ADD CONSTRAINT planner_additional_parameter_values_additional_parameter_ibfk
FOREIGN KEY (additional_parameter_id)
  REFERENCES planner_additional_parameters (id);

ALTER TABLE planner_additional_parameter_values
ADD CONSTRAINT planner_additional_parameter_values_unique
UNIQUE KEY (additional_parameter_id, `key`);
"""

DOWN_SQL = """
ALTER TABLE planner_additional_parameter_values
DROP FOREIGN KEY planner_additional_parameter_values_additional_parameter_ibfk;

DROP TABLE planner_additional_parameter_values;


ALTER TABLE planner_additional_parameters
DROP FOREIGN KEY planner_additional_parameters_plan_ibfk;

DROP TABLE planner_additional_parameters;
"""
