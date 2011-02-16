-- MySQL dump 10.11
--
-- Host: localhost    Database: autotest_web
-- ------------------------------------------------------
-- Server version	5.0.51a-3ubuntu5.5-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `afe_aborted_host_queue_entries`
--

DROP TABLE IF EXISTS `afe_aborted_host_queue_entries`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_aborted_host_queue_entries` (
  `queue_entry_id` int(11) NOT NULL,
  `aborted_by_id` int(11) NOT NULL,
  `aborted_on` datetime NOT NULL,
  PRIMARY KEY  (`queue_entry_id`),
  KEY `aborted_host_queue_entries_aborted_by_id_fk` (`aborted_by_id`),
  CONSTRAINT `aborted_host_queue_entries_aborted_by_id_fk` FOREIGN KEY (`aborted_by_id`) REFERENCES `afe_users` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `aborted_host_queue_entries_queue_entry_id_fk` FOREIGN KEY (`queue_entry_id`) REFERENCES `afe_host_queue_entries` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_acl_groups`
--

DROP TABLE IF EXISTS `afe_acl_groups`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_acl_groups` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) default NULL,
  `description` varchar(255) default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_acl_groups_hosts`
--

DROP TABLE IF EXISTS `afe_acl_groups_hosts`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_acl_groups_hosts` (
  `aclgroup_id` int(11) default NULL,
  `host_id` int(11) default NULL,
  UNIQUE KEY `acl_groups_hosts_both_ids` (`aclgroup_id`,`host_id`),
  KEY `acl_groups_hosts_host_id` (`host_id`),
  CONSTRAINT `acl_groups_hosts_aclgroup_id_fk` FOREIGN KEY (`aclgroup_id`) REFERENCES `afe_acl_groups` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `acl_groups_hosts_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_acl_groups_users`
--

DROP TABLE IF EXISTS `afe_acl_groups_users`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_acl_groups_users` (
  `aclgroup_id` int(11) default NULL,
  `user_id` int(11) default NULL,
  UNIQUE KEY `acl_groups_users_both_ids` (`aclgroup_id`,`user_id`),
  KEY `acl_groups_users_user_id` (`user_id`),
  CONSTRAINT `acl_groups_users_aclgroup_id_fk` FOREIGN KEY (`aclgroup_id`) REFERENCES `afe_acl_groups` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `acl_groups_users_user_id_fk` FOREIGN KEY (`user_id`) REFERENCES `afe_users` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_atomic_groups`
--

DROP TABLE IF EXISTS `afe_atomic_groups`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_atomic_groups` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) NOT NULL,
  `description` longtext,
  `max_number_of_machines` int(11) NOT NULL,
  `invalid` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_autotests`
--

DROP TABLE IF EXISTS `afe_autotests`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_autotests` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) default NULL,
  `test_class` varchar(255) default NULL,
  `description` text,
  `test_type` int(11) default NULL,
  `path` varchar(255) default NULL,
  `author` varchar(256) default NULL,
  `dependencies` varchar(256) default NULL,
  `experimental` smallint(6) default '0',
  `run_verify` smallint(6) default '1',
  `test_time` smallint(6) default '1',
  `test_category` varchar(256) default NULL,
  `sync_count` int(11) default '1',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_autotests_dependency_labels`
--

DROP TABLE IF EXISTS `afe_autotests_dependency_labels`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_autotests_dependency_labels` (
  `id` int(11) NOT NULL auto_increment,
  `test_id` int(11) NOT NULL,
  `label_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `test_id` (`test_id`,`label_id`),
  KEY `autotests_dependency_labels_label_id_fk` (`label_id`),
  CONSTRAINT `autotests_dependency_labels_label_id_fk` FOREIGN KEY (`label_id`) REFERENCES `afe_labels` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `autotests_dependency_labels_test_id_fk` FOREIGN KEY (`test_id`) REFERENCES `afe_autotests` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_host_attributes`
--

DROP TABLE IF EXISTS `afe_host_attributes`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_host_attributes` (
  `id` int(11) NOT NULL auto_increment,
  `host_id` int(11) NOT NULL,
  `attribute` varchar(90) NOT NULL,
  `value` varchar(300) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `host_id` (`host_id`),
  KEY `attribute` (`attribute`),
  CONSTRAINT `afe_host_attributes_ibfk_1` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_host_queue_entries`
--

DROP TABLE IF EXISTS `afe_host_queue_entries`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_host_queue_entries` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) default NULL,
  `host_id` int(11) default NULL,
  `status` varchar(255) default NULL,
  `meta_host` int(11) default NULL,
  `active` tinyint(1) default '0',
  `complete` tinyint(1) default '0',
  `deleted` tinyint(1) NOT NULL,
  `execution_subdir` varchar(255) NOT NULL,
  `atomic_group_id` int(11) default NULL,
  `aborted` tinyint(1) NOT NULL default '0',
  `started_on` datetime default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `host_queue_entries_job_id_and_host_id` (`job_id`,`host_id`),
  KEY `host_queue_entries_host_id` (`host_id`),
  KEY `host_queue_entries_meta_host` (`meta_host`),
  KEY `atomic_group_id` (`atomic_group_id`),
  CONSTRAINT `afe_host_queue_entries_ibfk_1` FOREIGN KEY (`atomic_group_id`) REFERENCES `afe_atomic_groups` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `host_queue_entries_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `host_queue_entries_job_id_fk` FOREIGN KEY (`job_id`) REFERENCES `afe_jobs` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `host_queue_entries_meta_host_fk` FOREIGN KEY (`meta_host`) REFERENCES `afe_labels` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_hosts`
--

DROP TABLE IF EXISTS `afe_hosts`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_hosts` (
  `id` int(11) NOT NULL auto_increment,
  `hostname` varchar(255) default NULL,
  `locked` tinyint(1) default '0',
  `synch_id` int(11) default NULL,
  `status` varchar(255) default NULL,
  `invalid` tinyint(1) default '0',
  `protection` int(11) NOT NULL,
  `locked_by_id` int(11) default NULL,
  `lock_time` datetime default NULL,
  `dirty` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `hosts_locked_by_fk` (`locked_by_id`),
  CONSTRAINT `hosts_locked_by_fk` FOREIGN KEY (`locked_by_id`) REFERENCES `afe_users` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_hosts_labels`
--

DROP TABLE IF EXISTS `afe_hosts_labels`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_hosts_labels` (
  `host_id` int(11) default NULL,
  `label_id` int(11) default NULL,
  UNIQUE KEY `hosts_labels_both_ids` (`label_id`,`host_id`),
  KEY `hosts_labels_host_id` (`host_id`),
  CONSTRAINT `hosts_labels_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `hosts_labels_label_id_fk` FOREIGN KEY (`label_id`) REFERENCES `afe_labels` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_ineligible_host_queues`
--

DROP TABLE IF EXISTS `afe_ineligible_host_queues`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_ineligible_host_queues` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) default NULL,
  `host_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `ineligible_host_queues_both_ids` (`host_id`,`job_id`),
  KEY `ineligible_host_queues_job_id` (`job_id`),
  CONSTRAINT `ineligible_host_queues_host_id_fk` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `ineligible_host_queues_job_id_fk` FOREIGN KEY (`job_id`) REFERENCES `afe_jobs` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_job_keyvals`
--

DROP TABLE IF EXISTS `afe_job_keyvals`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_job_keyvals` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) NOT NULL,
  `key` varchar(90) NOT NULL,
  `value` varchar(300) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `afe_job_keyvals_job_id` (`job_id`),
  KEY `afe_job_keyvals_key` (`key`),
  CONSTRAINT `afe_job_keyvals_ibfk_1` FOREIGN KEY (`job_id`) REFERENCES `afe_jobs` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_jobs`
--

DROP TABLE IF EXISTS `afe_jobs`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_jobs` (
  `id` int(11) NOT NULL auto_increment,
  `owner` varchar(255) default NULL,
  `name` varchar(255) default NULL,
  `priority` int(11) default NULL,
  `control_file` text,
  `control_type` int(11) default NULL,
  `created_on` datetime default NULL,
  `synch_count` int(11) default NULL,
  `timeout` int(11) NOT NULL,
  `run_verify` tinyint(1) default '1',
  `email_list` varchar(250) NOT NULL,
  `reboot_before` smallint(6) NOT NULL,
  `reboot_after` smallint(6) NOT NULL,
  `parse_failed_repair` tinyint(1) NOT NULL default '1',
  `max_runtime_hrs` int(11) NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_jobs_dependency_labels`
--

DROP TABLE IF EXISTS `afe_jobs_dependency_labels`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_jobs_dependency_labels` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) NOT NULL,
  `label_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `job_id` (`job_id`,`label_id`),
  KEY `jobs_dependency_labels_label_id_fk` (`label_id`),
  CONSTRAINT `jobs_dependency_labels_job_id_fk` FOREIGN KEY (`job_id`) REFERENCES `afe_jobs` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `jobs_dependency_labels_label_id_fk` FOREIGN KEY (`label_id`) REFERENCES `afe_labels` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_labels`
--

DROP TABLE IF EXISTS `afe_labels`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_labels` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(750) default NULL,
  `kernel_config` varchar(255) default NULL,
  `platform` tinyint(1) default '0',
  `invalid` tinyint(1) NOT NULL,
  `only_if_needed` tinyint(1) NOT NULL,
  `atomic_group_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `atomic_group_id` (`atomic_group_id`),
  CONSTRAINT `afe_labels_ibfk_1` FOREIGN KEY (`atomic_group_id`) REFERENCES `afe_atomic_groups` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_profilers`
--

DROP TABLE IF EXISTS `afe_profilers`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_profilers` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(255) NOT NULL,
  `description` longtext NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_recurring_run`
--

DROP TABLE IF EXISTS `afe_recurring_run`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_recurring_run` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(11) NOT NULL,
  `owner_id` int(11) NOT NULL,
  `start_date` datetime NOT NULL,
  `loop_period` int(11) NOT NULL,
  `loop_count` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `recurring_run_job_id` (`job_id`),
  KEY `recurring_run_owner_id` (`owner_id`),
  CONSTRAINT `recurring_run_job_id_fk` FOREIGN KEY (`job_id`) REFERENCES `afe_jobs` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `recurring_run_owner_id_fk` FOREIGN KEY (`owner_id`) REFERENCES `afe_users` (`id`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_special_tasks`
--

DROP TABLE IF EXISTS `afe_special_tasks`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_special_tasks` (
  `id` int(11) NOT NULL auto_increment,
  `host_id` int(11) NOT NULL,
  `task` varchar(64) NOT NULL,
  `time_requested` datetime NOT NULL,
  `is_active` tinyint(1) NOT NULL default '0',
  `is_complete` tinyint(1) NOT NULL default '0',
  `time_started` datetime default NULL,
  `queue_entry_id` int(11) default NULL,
  `success` tinyint(1) NOT NULL default '0',
  `requested_by_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  KEY `special_tasks_host_id` (`host_id`),
  KEY `special_tasks_host_queue_entry_id` (`queue_entry_id`),
  KEY `special_tasks_requested_by_id` (`requested_by_id`),
  CONSTRAINT `special_tasks_requested_by_id` FOREIGN KEY (`requested_by_id`) REFERENCES `afe_users` (`id`) ON DELETE NO ACTION,
  CONSTRAINT `special_tasks_to_hosts_ibfk` FOREIGN KEY (`host_id`) REFERENCES `afe_hosts` (`id`),
  CONSTRAINT `special_tasks_to_host_queue_entries_ibfk` FOREIGN KEY (`queue_entry_id`) REFERENCES `afe_host_queue_entries` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `afe_users`
--

DROP TABLE IF EXISTS `afe_users`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `afe_users` (
  `id` int(11) NOT NULL auto_increment,
  `login` varchar(255) default NULL,
  `access_level` int(11) default '0',
  `reboot_before` smallint(6) NOT NULL,
  `reboot_after` smallint(6) NOT NULL,
  `show_experimental` tinyint(1) NOT NULL default '0',
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `planner_autoprocess`
--

DROP TABLE IF EXISTS `planner_autoprocess`;
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
-- Table structure for table `planner_autoprocess_bugs`
--

DROP TABLE IF EXISTS `planner_autoprocess_bugs`;
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
-- Table structure for table `planner_autoprocess_keyvals`
--

DROP TABLE IF EXISTS `planner_autoprocess_keyvals`;
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

DROP TABLE IF EXISTS `planner_autoprocess_labels`;
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
-- Table structure for table `planner_bugs`
--

DROP TABLE IF EXISTS `planner_bugs`;
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
-- Table structure for table `planner_custom_queries`
--

DROP TABLE IF EXISTS `planner_custom_queries`;
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
-- Table structure for table `planner_data_types`
--

DROP TABLE IF EXISTS `planner_data_types`;
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
-- Table structure for table `planner_history`
--

DROP TABLE IF EXISTS `planner_history`;
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
-- Table structure for table `planner_hosts`
--

DROP TABLE IF EXISTS `planner_hosts`;
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
-- Table structure for table `planner_keyvals`
--

DROP TABLE IF EXISTS `planner_keyvals`;
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
-- Table structure for table `planner_plan_host_labels`
--

DROP TABLE IF EXISTS `planner_plan_host_labels`;
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
-- Table structure for table `planner_plan_owners`
--

DROP TABLE IF EXISTS `planner_plan_owners`;
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
-- Table structure for table `planner_plans`
--

DROP TABLE IF EXISTS `planner_plans`;
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
-- Table structure for table `planner_saved_objects`
--

DROP TABLE IF EXISTS `planner_saved_objects`;
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
-- Table structure for table `planner_test_configs`
--

DROP TABLE IF EXISTS `planner_test_configs`;
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
-- Table structure for table `planner_test_control_files`
--

DROP TABLE IF EXISTS `planner_test_control_files`;
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
-- Table structure for table `planner_test_jobs`
--

DROP TABLE IF EXISTS `planner_test_jobs`;
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
-- Table structure for table `planner_test_run_bugs`
--

DROP TABLE IF EXISTS `planner_test_run_bugs`;
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

--
-- Table structure for table `planner_test_runs`
--

DROP TABLE IF EXISTS `planner_test_runs`;
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
-- Table structure for table `tko_embedded_graphing_queries`
--

DROP TABLE IF EXISTS `tko_embedded_graphing_queries`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_embedded_graphing_queries` (
  `id` int(11) NOT NULL auto_increment,
  `url_token` text NOT NULL,
  `graph_type` varchar(16) NOT NULL,
  `params` text NOT NULL,
  `last_updated` datetime NOT NULL,
  `refresh_time` datetime default NULL,
  `cached_png` mediumblob,
  PRIMARY KEY  (`id`),
  KEY `url_token` (`url_token`(128))
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_iteration_attributes`
--

DROP TABLE IF EXISTS `tko_iteration_attributes`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_iteration_attributes` (
  `test_idx` int(10) unsigned NOT NULL,
  `iteration` int(11) default NULL,
  `attribute` varchar(30) default NULL,
  `value` varchar(1024) default NULL,
  KEY `test_idx` (`test_idx`),
  CONSTRAINT `tko_iteration_attributes_ibfk_1` FOREIGN KEY (`test_idx`) REFERENCES `tko_tests` (`test_idx`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_iteration_result`
--

DROP TABLE IF EXISTS `tko_iteration_result`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_iteration_result` (
  `test_idx` int(10) unsigned NOT NULL,
  `iteration` int(11) default NULL,
  `attribute` varchar(30) default NULL,
  `value` float default NULL,
  KEY `test_idx` (`test_idx`),
  KEY `attribute` (`attribute`),
  KEY `value` (`value`),
  CONSTRAINT `tko_iteration_result_ibfk_1` FOREIGN KEY (`test_idx`) REFERENCES `tko_tests` (`test_idx`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_job_keyvals`
--

DROP TABLE IF EXISTS `tko_job_keyvals`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_job_keyvals` (
  `id` int(11) NOT NULL auto_increment,
  `job_id` int(10) unsigned NOT NULL,
  `key` varchar(90) NOT NULL,
  `value` varchar(300) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `tko_job_keyvals_job_id` (`job_id`),
  KEY `tko_job_keyvals_key` (`key`),
  CONSTRAINT `tko_job_keyvals_ibfk_1` FOREIGN KEY (`job_id`) REFERENCES `tko_jobs` (`job_idx`) ON DELETE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_jobs`
--

DROP TABLE IF EXISTS `tko_jobs`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_jobs` (
  `job_idx` int(10) unsigned NOT NULL auto_increment,
  `tag` varchar(100) default NULL,
  `label` varchar(100) default NULL,
  `username` varchar(80) default NULL,
  `machine_idx` int(10) unsigned NOT NULL,
  `queued_time` datetime default NULL,
  `started_time` datetime default NULL,
  `finished_time` datetime default NULL,
  `afe_job_id` int(11) default NULL,
  PRIMARY KEY  (`job_idx`),
  UNIQUE KEY `tag` (`tag`),
  KEY `label` (`label`),
  KEY `username` (`username`),
  KEY `machine_idx` (`machine_idx`),
  KEY `afe_job_id` (`afe_job_id`),
  CONSTRAINT `tko_jobs_ibfk_1` FOREIGN KEY (`machine_idx`) REFERENCES `tko_machines` (`machine_idx`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_kernels`
--

DROP TABLE IF EXISTS `tko_kernels`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_kernels` (
  `kernel_idx` int(10) unsigned NOT NULL auto_increment,
  `kernel_hash` varchar(35) default NULL,
  `base` varchar(30) default NULL,
  `printable` varchar(100) default NULL,
  PRIMARY KEY  (`kernel_idx`),
  KEY `printable` (`printable`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_machines`
--

DROP TABLE IF EXISTS `tko_machines`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_machines` (
  `machine_idx` int(10) unsigned NOT NULL auto_increment,
  `hostname` varchar(700) default NULL,
  `machine_group` varchar(80) default NULL,
  `owner` varchar(80) default NULL,
  PRIMARY KEY  (`machine_idx`),
  UNIQUE KEY `hostname` (`hostname`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_patches`
--

DROP TABLE IF EXISTS `tko_patches`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_patches` (
  `kernel_idx` int(10) unsigned NOT NULL,
  `name` varchar(80) default NULL,
  `url` varchar(300) default NULL,
  `hash` varchar(35) default NULL,
  KEY `kernel_idx` (`kernel_idx`),
  CONSTRAINT `tko_patches_ibfk_1` FOREIGN KEY (`kernel_idx`) REFERENCES `tko_kernels` (`kernel_idx`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `tko_perf_view`
--

DROP TABLE IF EXISTS `tko_perf_view`;
/*!50001 DROP VIEW IF EXISTS `tko_perf_view`*/;
/*!50001 CREATE TABLE `tko_perf_view` (
  `test_idx` int(10) unsigned,
  `job_idx` int(10) unsigned,
  `test` varchar(60),
  `subdir` varchar(60),
  `kernel_idx` int(10) unsigned,
  `status` int(10) unsigned,
  `reason` varchar(1024),
  `machine_idx` int(10) unsigned,
  `test_started_time` datetime,
  `test_finished_time` datetime,
  `job_tag` varchar(100),
  `job_label` varchar(100),
  `job_username` varchar(80),
  `job_queued_time` datetime,
  `job_started_time` datetime,
  `job_finished_time` datetime,
  `machine_hostname` varchar(700),
  `machine_group` varchar(80),
  `machine_owner` varchar(80),
  `kernel_hash` varchar(35),
  `kernel_base` varchar(30),
  `kernel_printable` varchar(100),
  `status_word` varchar(10),
  `iteration` int(11),
  `iteration_key` varchar(30),
  `iteration_value` float
) */;

--
-- Temporary table structure for view `tko_perf_view_2`
--

DROP TABLE IF EXISTS `tko_perf_view_2`;
/*!50001 DROP VIEW IF EXISTS `tko_perf_view_2`*/;
/*!50001 CREATE TABLE `tko_perf_view_2` (
  `test_idx` int(10) unsigned,
  `job_idx` int(10) unsigned,
  `test_name` varchar(60),
  `subdir` varchar(60),
  `kernel_idx` int(10) unsigned,
  `status_idx` int(10) unsigned,
  `reason` varchar(1024),
  `machine_idx` int(10) unsigned,
  `test_started_time` datetime,
  `test_finished_time` datetime,
  `job_tag` varchar(100),
  `job_name` varchar(100),
  `job_owner` varchar(80),
  `job_queued_time` datetime,
  `job_started_time` datetime,
  `job_finished_time` datetime,
  `hostname` varchar(700),
  `platform` varchar(80),
  `machine_owner` varchar(80),
  `kernel_hash` varchar(35),
  `kernel_base` varchar(30),
  `kernel` varchar(100),
  `status` varchar(10),
  `iteration` int(11),
  `iteration_key` varchar(30),
  `iteration_value` float
) */;

--
-- Table structure for table `tko_query_history`
--

DROP TABLE IF EXISTS `tko_query_history`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_query_history` (
  `uid` varchar(32) default NULL,
  `time_created` varchar(32) default NULL,
  `user_comment` varchar(256) default NULL,
  `url` varchar(1000) default NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_saved_queries`
--

DROP TABLE IF EXISTS `tko_saved_queries`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_saved_queries` (
  `id` int(11) NOT NULL auto_increment,
  `owner` varchar(80) NOT NULL,
  `name` varchar(100) NOT NULL,
  `url_token` longtext NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_status`
--

DROP TABLE IF EXISTS `tko_status`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_status` (
  `status_idx` int(10) unsigned NOT NULL auto_increment,
  `word` varchar(10) default NULL,
  PRIMARY KEY  (`status_idx`),
  KEY `word` (`word`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Dumping data for table `tko_status`
--

LOCK TABLES `tko_status` WRITE;
/*!40000 ALTER TABLE `tko_status` DISABLE KEYS */;
INSERT INTO `tko_status` (word) VALUES ('ABORT'),('ALERT'),('ERROR'),('FAIL'),('GOOD'),('NOSTATUS'),('RUNNING'),('TEST_NA'),('WARN');
/*!40000 ALTER TABLE `tko_status` ENABLE KEYS */;
UNLOCK TABLES;


--
-- Table structure for table `tko_test_attributes`
--

DROP TABLE IF EXISTS `tko_test_attributes`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_test_attributes` (
  `test_idx` int(10) unsigned NOT NULL,
  `attribute` varchar(30) default NULL,
  `value` varchar(1024) default NULL,
  `id` int(11) NOT NULL auto_increment,
  `user_created` tinyint(1) NOT NULL default '0',
  PRIMARY KEY  (`id`),
  KEY `test_idx` (`test_idx`),
  KEY `attribute` (`attribute`),
  KEY `value` (`value`(767)),
  CONSTRAINT `tko_test_attributes_ibfk_1` FOREIGN KEY (`test_idx`) REFERENCES `tko_tests` (`test_idx`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_test_labels`
--

DROP TABLE IF EXISTS `tko_test_labels`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_test_labels` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(80) NOT NULL,
  `description` longtext NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `tko_test_labels_tests`
--

DROP TABLE IF EXISTS `tko_test_labels_tests`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_test_labels_tests` (
  `id` int(11) NOT NULL auto_increment,
  `testlabel_id` int(11) NOT NULL,
  `test_id` int(10) unsigned NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `testlabel_id` (`testlabel_id`,`test_id`),
  KEY `test_labels_tests_test_id` (`test_id`),
  CONSTRAINT `tests_labels_tests_ibfk_1` FOREIGN KEY (`testlabel_id`) REFERENCES `tko_test_labels` (`id`),
  CONSTRAINT `tests_labels_tests_ibfk_2` FOREIGN KEY (`test_id`) REFERENCES `tko_tests` (`test_idx`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `tko_test_view`
--

DROP TABLE IF EXISTS `tko_test_view`;
/*!50001 DROP VIEW IF EXISTS `tko_test_view`*/;
/*!50001 CREATE TABLE `tko_test_view` (
  `test_idx` int(10) unsigned,
  `job_idx` int(10) unsigned,
  `test` varchar(60),
  `subdir` varchar(60),
  `kernel_idx` int(10) unsigned,
  `status` int(10) unsigned,
  `reason` varchar(1024),
  `machine_idx` int(10) unsigned,
  `test_started_time` datetime,
  `test_finished_time` datetime,
  `job_tag` varchar(100),
  `job_label` varchar(100),
  `job_username` varchar(80),
  `job_queued_time` datetime,
  `job_started_time` datetime,
  `job_finished_time` datetime,
  `machine_hostname` varchar(700),
  `machine_group` varchar(80),
  `machine_owner` varchar(80),
  `kernel_hash` varchar(35),
  `kernel_base` varchar(30),
  `kernel_printable` varchar(100),
  `status_word` varchar(10)
) */;

--
-- Temporary table structure for view `tko_test_view_2`
--

DROP TABLE IF EXISTS `tko_test_view_2`;
/*!50001 DROP VIEW IF EXISTS `tko_test_view_2`*/;
/*!50001 CREATE TABLE `tko_test_view_2` (
  `test_idx` int(10) unsigned,
  `job_idx` int(10) unsigned,
  `test_name` varchar(60),
  `subdir` varchar(60),
  `kernel_idx` int(10) unsigned,
  `status_idx` int(10) unsigned,
  `reason` varchar(1024),
  `machine_idx` int(10) unsigned,
  `test_started_time` datetime,
  `test_finished_time` datetime,
  `job_tag` varchar(100),
  `job_name` varchar(100),
  `job_owner` varchar(80),
  `job_queued_time` datetime,
  `job_started_time` datetime,
  `job_finished_time` datetime,
  `afe_job_id` int(11),
  `hostname` varchar(700),
  `platform` varchar(80),
  `machine_owner` varchar(80),
  `kernel_hash` varchar(35),
  `kernel_base` varchar(30),
  `kernel` varchar(100),
  `status` varchar(10)
) */;

--
-- Temporary table structure for view `tko_test_view_outer_joins`
--

DROP TABLE IF EXISTS `tko_test_view_outer_joins`;
/*!50001 DROP VIEW IF EXISTS `tko_test_view_outer_joins`*/;
/*!50001 CREATE TABLE `tko_test_view_outer_joins` (
  `test_idx` int(10) unsigned,
  `job_idx` int(10) unsigned,
  `test_name` varchar(60),
  `subdir` varchar(60),
  `kernel_idx` int(10) unsigned,
  `status_idx` int(10) unsigned,
  `reason` varchar(1024),
  `machine_idx` int(10) unsigned,
  `test_started_time` datetime,
  `test_finished_time` datetime,
  `job_tag` varchar(100),
  `job_name` varchar(100),
  `job_owner` varchar(80),
  `job_queued_time` datetime,
  `job_started_time` datetime,
  `job_finished_time` datetime,
  `hostname` varchar(700),
  `platform` varchar(80),
  `machine_owner` varchar(80),
  `kernel_hash` varchar(35),
  `kernel_base` varchar(30),
  `kernel` varchar(100),
  `status` varchar(10)
) */;

--
-- Table structure for table `tko_tests`
--

DROP TABLE IF EXISTS `tko_tests`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `tko_tests` (
  `test_idx` int(10) unsigned NOT NULL auto_increment,
  `job_idx` int(10) unsigned NOT NULL,
  `test` varchar(60) default NULL,
  `subdir` varchar(60) default NULL,
  `kernel_idx` int(10) unsigned NOT NULL,
  `status` int(10) unsigned NOT NULL,
  `reason` varchar(1024) default NULL,
  `machine_idx` int(10) unsigned NOT NULL,
  `invalid` tinyint(1) default '0',
  `finished_time` datetime default NULL,
  `started_time` datetime default NULL,
  PRIMARY KEY  (`test_idx`),
  KEY `kernel_idx` (`kernel_idx`),
  KEY `status` (`status`),
  KEY `machine_idx` (`machine_idx`),
  KEY `job_idx` (`job_idx`),
  KEY `reason` (`reason`(767)),
  KEY `test` (`test`),
  KEY `subdir` (`subdir`),
  CONSTRAINT `tests_to_jobs_ibfk` FOREIGN KEY (`job_idx`) REFERENCES `tko_jobs` (`job_idx`),
  CONSTRAINT `tko_tests_ibfk_1` FOREIGN KEY (`kernel_idx`) REFERENCES `tko_kernels` (`kernel_idx`) ON DELETE CASCADE,
  CONSTRAINT `tko_tests_ibfk_2` FOREIGN KEY (`status`) REFERENCES `tko_status` (`status_idx`) ON DELETE CASCADE,
  CONSTRAINT `tko_tests_ibfk_3` FOREIGN KEY (`machine_idx`) REFERENCES `tko_machines` (`machine_idx`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
SET character_set_client = @saved_cs_client;

--
-- Final view structure for view `tko_perf_view`
--

/*!50001 DROP TABLE `tko_perf_view`*/;
/*!50001 DROP VIEW IF EXISTS `tko_perf_view`*/;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=CURRENT_USER SQL SECURITY DEFINER */
/*!50001 VIEW `tko_perf_view` AS select `tko_tests`.`test_idx` AS `test_idx`,`tko_tests`.`job_idx` AS `job_idx`,`tko_tests`.`test` AS `test`,`tko_tests`.`subdir` AS `subdir`,`tko_tests`.`kernel_idx` AS `kernel_idx`,`tko_tests`.`status` AS `status`,`tko_tests`.`reason` AS `reason`,`tko_tests`.`machine_idx` AS `machine_idx`,`tko_tests`.`started_time` AS `test_started_time`,`tko_tests`.`finished_time` AS `test_finished_time`,`tko_jobs`.`tag` AS `job_tag`,`tko_jobs`.`label` AS `job_label`,`tko_jobs`.`username` AS `job_username`,`tko_jobs`.`queued_time` AS `job_queued_time`,`tko_jobs`.`started_time` AS `job_started_time`,`tko_jobs`.`finished_time` AS `job_finished_time`,`tko_machines`.`hostname` AS `machine_hostname`,`tko_machines`.`machine_group` AS `machine_group`,`tko_machines`.`owner` AS `machine_owner`,`tko_kernels`.`kernel_hash` AS `kernel_hash`,`tko_kernels`.`base` AS `kernel_base`,`tko_kernels`.`printable` AS `kernel_printable`,`tko_status`.`word` AS `status_word`,`tko_iteration_result`.`iteration` AS `iteration`,`tko_iteration_result`.`attribute` AS `iteration_key`,`tko_iteration_result`.`value` AS `iteration_value` from (((((`tko_tests` join `tko_jobs` on((`tko_jobs`.`job_idx` = `tko_tests`.`job_idx`))) join `tko_machines` on((`tko_machines`.`machine_idx` = `tko_jobs`.`machine_idx`))) join `tko_kernels` on((`tko_kernels`.`kernel_idx` = `tko_tests`.`kernel_idx`))) join `tko_status` on((`tko_status`.`status_idx` = `tko_tests`.`status`))) join `tko_iteration_result` on((`tko_iteration_result`.`test_idx` = `tko_tests`.`test_idx`))) */;

--
-- Final view structure for view `tko_perf_view_2`
--

/*!50001 DROP TABLE `tko_perf_view_2`*/;
/*!50001 DROP VIEW IF EXISTS `tko_perf_view_2`*/;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=CURRENT_USER SQL SECURITY DEFINER */
/*!50001 VIEW `tko_perf_view_2` AS select `tko_tests`.`test_idx` AS `test_idx`,`tko_tests`.`job_idx` AS `job_idx`,`tko_tests`.`test` AS `test_name`,`tko_tests`.`subdir` AS `subdir`,`tko_tests`.`kernel_idx` AS `kernel_idx`,`tko_tests`.`status` AS `status_idx`,`tko_tests`.`reason` AS `reason`,`tko_tests`.`machine_idx` AS `machine_idx`,`tko_tests`.`started_time` AS `test_started_time`,`tko_tests`.`finished_time` AS `test_finished_time`,`tko_jobs`.`tag` AS `job_tag`,`tko_jobs`.`label` AS `job_name`,`tko_jobs`.`username` AS `job_owner`,`tko_jobs`.`queued_time` AS `job_queued_time`,`tko_jobs`.`started_time` AS `job_started_time`,`tko_jobs`.`finished_time` AS `job_finished_time`,`tko_machines`.`hostname` AS `hostname`,`tko_machines`.`machine_group` AS `platform`,`tko_machines`.`owner` AS `machine_owner`,`tko_kernels`.`kernel_hash` AS `kernel_hash`,`tko_kernels`.`base` AS `kernel_base`,`tko_kernels`.`printable` AS `kernel`,`tko_status`.`word` AS `status`,`tko_iteration_result`.`iteration` AS `iteration`,`tko_iteration_result`.`attribute` AS `iteration_key`,`tko_iteration_result`.`value` AS `iteration_value` from (((((`tko_tests` left join `tko_jobs` on((`tko_jobs`.`job_idx` = `tko_tests`.`job_idx`))) left join `tko_machines` on((`tko_machines`.`machine_idx` = `tko_jobs`.`machine_idx`))) left join `tko_kernels` on((`tko_kernels`.`kernel_idx` = `tko_tests`.`kernel_idx`))) left join `tko_status` on((`tko_status`.`status_idx` = `tko_tests`.`status`))) left join `tko_iteration_result` on((`tko_iteration_result`.`test_idx` = `tko_tests`.`test_idx`))) */;

--
-- Final view structure for view `tko_test_view`
--

/*!50001 DROP TABLE `tko_test_view`*/;
/*!50001 DROP VIEW IF EXISTS `tko_test_view`*/;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=CURRENT_USER SQL SECURITY DEFINER */
/*!50001 VIEW `tko_test_view` AS select `tko_tests`.`test_idx` AS `test_idx`,`tko_tests`.`job_idx` AS `job_idx`,`tko_tests`.`test` AS `test`,`tko_tests`.`subdir` AS `subdir`,`tko_tests`.`kernel_idx` AS `kernel_idx`,`tko_tests`.`status` AS `status`,`tko_tests`.`reason` AS `reason`,`tko_tests`.`machine_idx` AS `machine_idx`,`tko_tests`.`started_time` AS `test_started_time`,`tko_tests`.`finished_time` AS `test_finished_time`,`tko_jobs`.`tag` AS `job_tag`,`tko_jobs`.`label` AS `job_label`,`tko_jobs`.`username` AS `job_username`,`tko_jobs`.`queued_time` AS `job_queued_time`,`tko_jobs`.`started_time` AS `job_started_time`,`tko_jobs`.`finished_time` AS `job_finished_time`,`tko_machines`.`hostname` AS `machine_hostname`,`tko_machines`.`machine_group` AS `machine_group`,`tko_machines`.`owner` AS `machine_owner`,`tko_kernels`.`kernel_hash` AS `kernel_hash`,`tko_kernels`.`base` AS `kernel_base`,`tko_kernels`.`printable` AS `kernel_printable`,`tko_status`.`word` AS `status_word` from ((((`tko_tests` join `tko_jobs` on((`tko_jobs`.`job_idx` = `tko_tests`.`job_idx`))) join `tko_machines` on((`tko_machines`.`machine_idx` = `tko_jobs`.`machine_idx`))) join `tko_kernels` on((`tko_kernels`.`kernel_idx` = `tko_tests`.`kernel_idx`))) join `tko_status` on((`tko_status`.`status_idx` = `tko_tests`.`status`))) */;

--
-- Final view structure for view `tko_test_view_2`
--

/*!50001 DROP TABLE `tko_test_view_2`*/;
/*!50001 DROP VIEW IF EXISTS `tko_test_view_2`*/;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=CURRENT_USER SQL SECURITY DEFINER */
/*!50001 VIEW `tko_test_view_2` AS select `tko_tests`.`test_idx` AS `test_idx`,`tko_tests`.`job_idx` AS `job_idx`,`tko_tests`.`test` AS `test_name`,`tko_tests`.`subdir` AS `subdir`,`tko_tests`.`kernel_idx` AS `kernel_idx`,`tko_tests`.`status` AS `status_idx`,`tko_tests`.`reason` AS `reason`,`tko_tests`.`machine_idx` AS `machine_idx`,`tko_tests`.`started_time` AS `test_started_time`,`tko_tests`.`finished_time` AS `test_finished_time`,`tko_jobs`.`tag` AS `job_tag`,`tko_jobs`.`label` AS `job_name`,`tko_jobs`.`username` AS `job_owner`,`tko_jobs`.`queued_time` AS `job_queued_time`,`tko_jobs`.`started_time` AS `job_started_time`,`tko_jobs`.`finished_time` AS `job_finished_time`,`tko_jobs`.`afe_job_id` AS `afe_job_id`,`tko_machines`.`hostname` AS `hostname`,`tko_machines`.`machine_group` AS `platform`,`tko_machines`.`owner` AS `machine_owner`,`tko_kernels`.`kernel_hash` AS `kernel_hash`,`tko_kernels`.`base` AS `kernel_base`,`tko_kernels`.`printable` AS `kernel`,`tko_status`.`word` AS `status` from ((((`tko_tests` join `tko_jobs` on((`tko_jobs`.`job_idx` = `tko_tests`.`job_idx`))) join `tko_machines` on((`tko_machines`.`machine_idx` = `tko_jobs`.`machine_idx`))) join `tko_kernels` on((`tko_kernels`.`kernel_idx` = `tko_tests`.`kernel_idx`))) join `tko_status` on((`tko_status`.`status_idx` = `tko_tests`.`status`))) */;

--
-- Final view structure for view `tko_test_view_outer_joins`
--

/*!50001 DROP TABLE `tko_test_view_outer_joins`*/;
/*!50001 DROP VIEW IF EXISTS `tko_test_view_outer_joins`*/;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=CURRENT_USER SQL SECURITY DEFINER */
/*!50001 VIEW `tko_test_view_outer_joins` AS select `tko_tests`.`test_idx` AS `test_idx`,`tko_tests`.`job_idx` AS `job_idx`,`tko_tests`.`test` AS `test_name`,`tko_tests`.`subdir` AS `subdir`,`tko_tests`.`kernel_idx` AS `kernel_idx`,`tko_tests`.`status` AS `status_idx`,`tko_tests`.`reason` AS `reason`,`tko_tests`.`machine_idx` AS `machine_idx`,`tko_tests`.`started_time` AS `test_started_time`,`tko_tests`.`finished_time` AS `test_finished_time`,`tko_jobs`.`tag` AS `job_tag`,`tko_jobs`.`label` AS `job_name`,`tko_jobs`.`username` AS `job_owner`,`tko_jobs`.`queued_time` AS `job_queued_time`,`tko_jobs`.`started_time` AS `job_started_time`,`tko_jobs`.`finished_time` AS `job_finished_time`,`tko_machines`.`hostname` AS `hostname`,`tko_machines`.`machine_group` AS `platform`,`tko_machines`.`owner` AS `machine_owner`,`tko_kernels`.`kernel_hash` AS `kernel_hash`,`tko_kernels`.`base` AS `kernel_base`,`tko_kernels`.`printable` AS `kernel`,`tko_status`.`word` AS `status` from ((((`tko_tests` left join `tko_jobs` on((`tko_jobs`.`job_idx` = `tko_tests`.`job_idx`))) left join `tko_machines` on((`tko_machines`.`machine_idx` = `tko_jobs`.`machine_idx`))) left join `tko_kernels` on((`tko_kernels`.`kernel_idx` = `tko_tests`.`kernel_idx`))) left join `tko_status` on((`tko_status`.`status_idx` = `tko_tests`.`status`))) */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2010-03-09 21:20:11
