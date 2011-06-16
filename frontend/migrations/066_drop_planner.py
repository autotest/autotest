UP_SQL = """
DROP TABLE IF EXISTS planner_test_run_bugs;
DROP TABLE IF EXISTS planner_test_runs;
DROP TABLE IF EXISTS planner_history;
DROP TABLE IF EXISTS planner_autoprocess_bugs;
DROP TABLE IF EXISTS planner_bugs;
DROP TABLE IF EXISTS planner_hosts;
DROP TABLE IF EXISTS planner_additional_parameter_values;
DROP TABLE IF EXISTS planner_additional_parameters;
DROP TABLE IF EXISTS planner_autoprocess_labels;
DROP TABLE IF EXISTS planner_autoprocess_keyvals;
DROP TABLE IF EXISTS planner_autoprocess;
DROP TABLE IF EXISTS planner_custom_queries;
DROP TABLE IF EXISTS planner_plan_host_labels;
DROP TABLE IF EXISTS planner_plan_owners;
DROP TABLE IF EXISTS planner_saved_objects;
DROP TABLE IF EXISTS planner_test_configs_skipped_hosts;
DROP TABLE IF EXISTS planner_test_jobs;
DROP TABLE IF EXISTS planner_data_types;
DROP TABLE IF EXISTS planner_keyvals;
DROP TABLE IF EXISTS planner_test_configs;
DROP TABLE IF EXISTS planner_test_control_files;
DROP TABLE IF EXISTS planner_plans;
"""

DOWN_SQL = """
--
-- Table structure for table `planner_plans`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_plans` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) NOT NULL,
  `label_override` varchar(255) default NULL,
  `support` longtext NOT NULL,
  `complete` tinyint(1) NOT NULL,
  `dirty` tinyint(1) NOT NULL,
  `initialized` tinyint(1) default '0',
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_test_control_files`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_test_control_files` (
  `id` int(11) NOT NULL auto_increment,
  `the_hash` varchar(40) NOT NULL,
  `contents` longtext NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `the_hash` (`the_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_test_configs`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_test_configs` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `control_file_id` int(11) NOT NULL,
  `execution_order` int(11) NOT NULL,
  `alias` varchar(255) NOT NULL,
  `estimated_runtime` int(11) NOT NULL,
  `is_server` tinyint(1) default '1',
  PRIMARY KEY  (`id`),
  UNIQUE KEY `tests_plan_id_alias_unique` (`plan_id`,`alias`),
  KEY `planner_tests_plan_id` (`plan_id`),
  KEY `planner_tests_control_file_id` (`control_file_id`),
  CONSTRAINT `tests_control_file_id_fk` FOREIGN KEY (`control_file_id`) REFERENCES `planner_test_control_files` (`id`),
  CONSTRAINT `tests_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_keyvals`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_keyvals` (
  `id` int(11) NOT NULL auto_increment,
  `the_hash` varchar(40) NOT NULL,
  `key` varchar(1024) NOT NULL,
  `value` varchar(1024) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `the_hash` (`the_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_data_types`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_data_types` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) NOT NULL,
  `db_table` varchar(255) NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_test_jobs`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_test_jobs` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `test_config_id` int(11) NOT NULL,
  `afe_job_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `planner_test_jobs_plan_id` (`plan_id`),
  KEY `planner_test_jobs_afe_job_id` (`afe_job_id`),
  KEY `planner_test_jobs_test_config_id` (`test_config_id`),
  CONSTRAINT `test_jobs_afe_job_id_fk` FOREIGN KEY (`afe_job_id`) REFERENCES `afe_jobs` (`id`),
  CONSTRAINT `test_jobs_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`),
  CONSTRAINT `test_jobs_test_config_id_fk` FOREIGN KEY (`test_config_id`) REFERENCES `planner_test_configs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_test_configs_skipped_hosts`
--

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

--
-- Table structure for table `planner_saved_objects`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_saved_objects` (
  `id` int(11) NOT NULL auto_increment,
  `user_id` int(11) NOT NULL,
  `type` varchar(16) NOT NULL,
  `name` varchar(255) NOT NULL,
  `encoded_object` longtext NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `user_id` (`user_id`,`type`,`name`),
  KEY `planner_saved_objects_user_id` (`user_id`),
  CONSTRAINT `saved_objects_user_id_fk` FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_plan_owners`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_plan_owners` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `plan_id` (`plan_id`,`user_id`),
  KEY `plan_owners_user_id_fk` (`user_id`),
  CONSTRAINT `plan_owners_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`),
  CONSTRAINT `plan_owners_user_id_fk` FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_plan_host_labels`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_plan_host_labels` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `label_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `plan_host_labels_plan_id_fk` (`plan_id`),
  KEY `plan_host_labels_label_id_fk` (`label_id`),
  CONSTRAINT `plan_host_labels_label_id_fk` FOREIGN KEY (`label_id`) REFERENCES `afe_labels` (`id`),
  CONSTRAINT `plan_host_labels_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_custom_queries`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_custom_queries` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `query` longtext NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `planner_custom_queries_plan_id` (`plan_id`),
  CONSTRAINT `custom_queries_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_autoprocess`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_autoprocess` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `condition` longtext NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `reason_override` varchar(255) default NULL,
  PRIMARY KEY  (`id`),
  KEY `planner_autoprocess_plan_id` (`plan_id`),
  CONSTRAINT `autoprocess_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_autoprocess_keyvals`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_autoprocess_keyvals` (
  `id` int(11) NOT NULL auto_increment,
  `autoprocess_id` int(11) NOT NULL,
  `keyval_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `autoprocess_id` (`autoprocess_id`,`keyval_id`),
  KEY `autoprocess_keyvals_keyval_id_fk` (`keyval_id`),
  CONSTRAINT `autoprocess_keyvals_autoprocess_id_fk` FOREIGN KEY (`autoprocess_id`) REFERENCES `planner_autoprocess` (`id`),
  CONSTRAINT `autoprocess_keyvals_keyval_id_fk` FOREIGN KEY (`keyval_id`) REFERENCES `planner_keyvals` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_autoprocess_labels`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_autoprocess_labels` (
  `id` int(11) NOT NULL auto_increment,
  `autoprocess_id` int(11) NOT NULL,
  `testlabel_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `autoprocess_id` (`autoprocess_id`,`testlabel_id`),
  KEY `autoprocess_labels_testlabel_id_fk` (`testlabel_id`),
  CONSTRAINT `autoprocess_labels_autoprocess_id_fk` FOREIGN KEY (`autoprocess_id`) REFERENCES `planner_autoprocess` (`id`),
  CONSTRAINT `autoprocess_labels_testlabel_id_fk` FOREIGN KEY (`testlabel_id`) REFERENCES `tko_test_labels` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_additional_parameters`
--

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

--
-- Table structure for table `planner_additional_parameter_values`
--

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

--
-- Table structure for table `planner_hosts`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_hosts` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `host_id` int(11) NOT NULL,
  `complete` tinyint(1) NOT NULL,
  `blocked` tinyint(1) NOT NULL,
  `added_by_label` tinyint(1) default '0',
  PRIMARY KEY  (`id`),
  KEY `planner_hosts_plan_id` (`plan_id`),
  KEY `planner_hosts_host_id` (`host_id`),
  CONSTRAINT `hosts_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`),
  CONSTRAINT `hosts_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_bugs`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_bugs` (
  `id` int(11) NOT NULL auto_increment,
  `external_uid` varchar(255) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `external_uid` (`external_uid`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_autoprocess_bugs`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_autoprocess_bugs` (
  `id` int(11) NOT NULL auto_increment,
  `autoprocess_id` int(11) NOT NULL,
  `bug_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `autoprocess_id` (`autoprocess_id`,`bug_id`),
  KEY `autoprocess_bugs_bug_id_fk` (`bug_id`),
  CONSTRAINT `autoprocess_bugs_autoprocess_id_fk` FOREIGN KEY (`autoprocess_id`) REFERENCES `planner_autoprocess` (`id`),
  CONSTRAINT `autoprocess_bugs_bug_id_fk` FOREIGN KEY (`bug_id`) REFERENCES `planner_bugs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_history`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_history` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `action_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `data_type_id` int(11) NOT NULL,
  `object_id` int(11) NOT NULL,
  `old_object_repr` longtext NOT NULL,
  `new_object_repr` longtext NOT NULL,
  `time` datetime NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `planner_history_plan_id` (`plan_id`),
  KEY `planner_history_user_id` (`user_id`),
  KEY `planner_history_data_type_id` (`data_type_id`),
  CONSTRAINT `history_data_type_id_fk` FOREIGN KEY (`data_type_id`) REFERENCES `planner_data_types` (`id`),
  CONSTRAINT `history_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`),
  CONSTRAINT `history_user_id_fk` FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_test_runs`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_test_runs` (
  `id` int(11) NOT NULL auto_increment,
  `plan_id` int(11) NOT NULL,
  `test_job_id` int(11) NOT NULL,
  `tko_test_id` int(10) unsigned NOT NULL,
  `status` varchar(16) NOT NULL,
  `finalized` tinyint(1) NOT NULL,
  `seen` tinyint(1) NOT NULL,
  `triaged` tinyint(1) NOT NULL,
  `host_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `test_runs_unique` (`plan_id`,`test_job_id`,`tko_test_id`,`host_id`),
  KEY `planner_test_runs_plan_id` (`plan_id`),
  KEY `planner_test_runs_test_job_id` (`test_job_id`),
  KEY `planner_test_runs_tko_test_id` (`tko_test_id`),
  KEY `test_runs_host_id_fk` (`host_id`),
  CONSTRAINT `test_runs_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `planner_hosts` (`id`),
  CONSTRAINT `test_runs_plan_id_fk` FOREIGN KEY (`plan_id`) REFERENCES `planner_plans` (`id`),
  CONSTRAINT `test_runs_test_job_id_fk` FOREIGN KEY (`test_job_id`) REFERENCES `planner_test_jobs` (`id`),
  CONSTRAINT `test_runs_tko_test_id_fk` FOREIGN KEY (`tko_test_id`) REFERENCES `tko_tests` (`test_idx`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_test_run_bugs`
--

SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `planner_test_run_bugs` (
  `id` int(11) NOT NULL auto_increment,
  `testrun_id` int(11) NOT NULL,
  `bug_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `testrun_id` (`testrun_id`,`bug_id`),
  KEY `test_run_bugs_bug_id_fk` (`bug_id`),
  CONSTRAINT `test_run_bugs_bug_id_fk` FOREIGN KEY (`bug_id`) REFERENCES `planner_bugs` (`id`),
  CONSTRAINT `test_run_bugs_testrun_id_fk` FOREIGN KEY (`testrun_id`) REFERENCES `planner_test_runs` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;
"""
