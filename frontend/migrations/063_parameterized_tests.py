UP_SQL = """
CREATE TABLE afe_test_parameters (
  id INT PRIMARY KEY AUTO_INCREMENT,
  test_id INT NOT NULL,
  name VARCHAR(255) NOT NULL
) ENGINE = InnoDB;

ALTER TABLE afe_test_parameters
ADD CONSTRAINT afe_test_parameters_test_ibfk
FOREIGN KEY (test_id) REFERENCES afe_autotests (id);

ALTER TABLE afe_test_parameters
ADD CONSTRAINT afe_test_parameters_unique
UNIQUE KEY (test_id, name);


CREATE TABLE afe_parameterized_jobs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  test_id INT NOT NULL,
  label_id INT DEFAULT NULL,
  use_container TINYINT(1) DEFAULT 0,
  profile_only TINYINT(1) DEFAULT 0,
  upload_kernel_config TINYINT(1) DEFAULT 0
) ENGINE = InnoDB;

ALTER TABLE afe_parameterized_jobs
ADD CONSTRAINT afe_parameterized_jobs_test_ibfk
FOREIGN KEY (test_id) REFERENCES afe_autotests (id);

ALTER TABLE afe_parameterized_jobs
ADD CONSTRAINT afe_parameterized_jobs_label_ibfk
FOREIGN KEY (label_id) REFERENCES afe_labels (id);


CREATE TABLE afe_kernels (
  id INT PRIMARY KEY AUTO_INCREMENT,
  version VARCHAR(255) NOT NULL,
  cmdline VARCHAR(255) DEFAULT ''
) ENGINE = InnoDB;

ALTER TABLE afe_kernels
ADD CONSTRAINT afe_kernals_unique
UNIQUE KEY (version, cmdline);


CREATE TABLE afe_parameterized_jobs_kernels (
  parameterized_job_id INT NOT NULL,
  kernel_id INT NOT NULL,
  PRIMARY KEY (parameterized_job_id, kernel_id)
) ENGINE = InnoDB;

ALTER TABLE afe_parameterized_jobs_kernels
ADD CONSTRAINT afe_parameterized_jobs_kernels_parameterized_job_ibfk
FOREIGN KEY (parameterized_job_id) REFERENCES afe_parameterized_jobs (id);


CREATE TABLE afe_parameterized_jobs_profilers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  parameterized_job_id INT NOT NULL,
  profiler_id INT NOT NULL
) ENGINE = InnoDB;

ALTER TABLE afe_parameterized_jobs_profilers
ADD CONSTRAINT afe_parameterized_jobs_profilers_parameterized_job_ibfk
FOREIGN KEY (parameterized_job_id) REFERENCES afe_parameterized_jobs (id);

ALTER TABLE afe_parameterized_jobs_profilers
ADD CONSTRAINT afe_parameterized_jobs_profilers_profile_ibfk
FOREIGN KEY (profiler_id) REFERENCES afe_profilers (id);

ALTER TABLE afe_parameterized_jobs_profilers
ADD CONSTRAINT afe_parameterized_jobs_profilers_unique
UNIQUE KEY (parameterized_job_id, profiler_id);


CREATE TABLE afe_parameterized_job_profiler_parameters (
  id INT PRIMARY KEY AUTO_INCREMENT,
  parameterized_job_profiler_id INT NOT NULL,
  parameter_name VARCHAR(255) NOT NULL,
  parameter_value TEXT NOT NULL,
  parameter_type ENUM('int', 'float', 'string')
) ENGINE = InnoDB;

ALTER TABLE afe_parameterized_job_profiler_parameters
ADD CONSTRAINT afe_parameterized_job_profiler_parameters_ibfk
FOREIGN KEY (parameterized_job_profiler_id)
  REFERENCES afe_parameterized_jobs_profilers (id);

ALTER TABLE afe_parameterized_job_profiler_parameters
ADD CONSTRAINT afe_parameterized_job_profiler_parameters_unique
UNIQUE KEY (parameterized_job_profiler_id, parameter_name);


CREATE TABLE afe_parameterized_job_parameters (
  id INT PRIMARY KEY AUTO_INCREMENT,
  parameterized_job_id INT NOT NULL,
  test_parameter_id INT NOT NULL,
  parameter_value TEXT NOT NULL,
  parameter_type ENUM('int', 'float', 'string')
) ENGINE = InnoDB;

ALTER TABLE afe_parameterized_job_parameters
ADD CONSTRAINT afe_parameterized_job_parameters_job_ibfk
FOREIGN KEY (parameterized_job_id) REFERENCES afe_parameterized_jobs (id);

ALTER TABLE afe_parameterized_job_parameters
ADD CONSTRAINT afe_parameterized_job_parameters_test_parameter_ibfk
FOREIGN KEY (test_parameter_id) REFERENCES afe_test_parameters (id);

ALTER TABLE afe_parameterized_job_parameters
ADD CONSTRAINT afe_parameterized_job_parameters_unique
UNIQUE KEY (parameterized_job_id, test_parameter_id);


ALTER TABLE afe_jobs
MODIFY COLUMN control_file TEXT DEFAULT NULL;

ALTER TABLE afe_jobs
ADD COLUMN parameterized_job_id INT DEFAULT NULL;

ALTER TABLE afe_jobs
ADD CONSTRAINT afe_jobs_parameterized_job_ibfk
FOREIGN KEY (parameterized_job_id) REFERENCES afe_parameterized_jobs (id);
"""


DOWN_SQL = """
ALTER TABLE afe_jobs
DROP FOREIGN KEY afe_jobs_parameterized_job_ibfk;

ALTER TABLE afe_jobs
DROP COLUMN parameterized_job_id;

ALTER TABLE afe_jobs
MODIFY COLUMN control_file TEXT;

DROP TABLE afe_parameterized_job_parameters;
DROP TABLE afe_parameterized_job_profiler_parameters;
DROP TABLE afe_parameterized_jobs_profilers;
DROP TABLE afe_parameterized_jobs_kernels;
DROP TABLE afe_kernels;
DROP TABLE afe_parameterized_jobs;
DROP TABLE afe_test_parameters;
"""
