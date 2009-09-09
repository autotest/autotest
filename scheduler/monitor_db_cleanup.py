"""
Autotest AFE Cleanup used by the scheduler
"""


import datetime, time, logging
import common
from autotest_lib.database import database_connection
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import email_manager, scheduler_config


class PeriodicCleanup(object):


    def __init__(self, db, clean_interval, run_at_initialize=False):
        self._db = db
        self.clean_interval = clean_interval
        self._last_clean_time = time.time()
        self._run_at_initialize = run_at_initialize


    def initialize(self):
        if self._run_at_initialize:
            self._cleanup()


    def run_cleanup_maybe(self):
        should_cleanup = (self._last_clean_time + self.clean_interval * 60
                          < time.time())
        if should_cleanup:
            self._cleanup()
            self._last_clean_time = time.time()


    def _cleanup(self):
        """Abrstract cleanup method."""
        raise NotImplementedError


class UserCleanup(PeriodicCleanup):
    """User cleanup that is controlled by the global config variable
       clean_interval in the SCHEDULER section.
    """


    def __init__(self, db, clean_interval_minutes):
        super(UserCleanup, self).__init__(db, clean_interval_minutes)


    def _cleanup(self):
        logging.info('Running periodic cleanup')
        self._abort_timed_out_jobs()
        self._abort_jobs_past_synch_start_timeout()
        self._abort_jobs_past_max_runtime()
        self._clear_inactive_blocks()
        self._check_for_db_inconsistencies()


    def _abort_timed_out_jobs(self):
        msg = 'Aborting all jobs that have timed out and are not complete'
        logging.info(msg)
        query = models.Job.objects.filter(hostqueueentry__complete=False).extra(
            where=['created_on + INTERVAL timeout HOUR < NOW()'])
        for job in query.distinct():
            logging.warning('Aborting job %d due to job timeout', job.id)
            job.abort(None)


    def _abort_jobs_past_synch_start_timeout(self):
        """
        Abort synchronous jobs that are past the start timeout (from global
        config) and are holding a machine that's in everyone.
        """
        msg = 'Aborting synchronous jobs that are past the start timeout'
        logging.info(msg)
        timeout_delta = datetime.timedelta(
            minutes=scheduler_config.config.synch_job_start_timeout_minutes)
        timeout_start = datetime.datetime.now() - timeout_delta
        query = models.Job.objects.filter(
            created_on__lt=timeout_start,
            hostqueueentry__status='Pending',
            hostqueueentry__host__aclgroup__name='Everyone')
        for job in query.distinct():
            logging.warning('Aborting job %d due to start timeout', job.id)
            entries_to_abort = job.hostqueueentry_set.exclude(
                status=models.HostQueueEntry.Status.RUNNING)
            for queue_entry in entries_to_abort:
                queue_entry.abort(None)


    def _abort_jobs_past_max_runtime(self):
        """
        Abort executions that have started and are past the job's max runtime.
        """
        logging.info('Aborting all jobs that have passed maximum runtime')
        rows = self._db.execute("""
            SELECT hqe.id
            FROM host_queue_entries AS hqe
            INNER JOIN jobs ON (hqe.job_id = jobs.id)
            WHERE NOT hqe.complete AND NOT hqe.aborted AND
            hqe.started_on + INTERVAL jobs.max_runtime_hrs HOUR < NOW()""")
        query = models.HostQueueEntry.objects.filter(
            id__in=[row[0] for row in rows])
        for queue_entry in query.distinct():
            logging.warning('Aborting entry %s due to max runtime', queue_entry)
            queue_entry.abort(None)


    def _check_for_db_inconsistencies(self):
        logging.info('Cleaning db inconsistencies')
        self._check_all_invalid_related_objects()


    def _check_invalid_related_objects_one_way(self, first_model,
                                               relation_field, second_model):
        if 'invalid' not in first_model.get_field_dict():
            return []
        invalid_objects = list(first_model.objects.filter(invalid=True))
        first_model.objects.populate_relationships(invalid_objects,
                                                   second_model,
                                                   'related_objects')
        error_lines = []
        for invalid_object in invalid_objects:
            if invalid_object.related_objects:
                related_list = ', '.join(str(related_object) for related_object
                                         in invalid_object.related_objects)
                error_lines.append('Invalid %s %s is related to %ss: %s'
                                   % (first_model.__name__, invalid_object,
                                      second_model.__name__, related_list))
                related_manager = getattr(invalid_object, relation_field)
                related_manager.clear()
        return error_lines


    def _check_invalid_related_objects(self, first_model, first_field,
                                       second_model, second_field):
        errors = self._check_invalid_related_objects_one_way(
            first_model, first_field, second_model)
        errors.extend(self._check_invalid_related_objects_one_way(
            second_model, second_field, first_model))
        return errors


    def _check_all_invalid_related_objects(self):
        model_pairs = ((models.Host, 'labels', models.Label, 'host_set'),
                       (models.AclGroup, 'hosts', models.Host, 'aclgroup_set'),
                       (models.AclGroup, 'users', models.User, 'aclgroup_set'),
                       (models.Test, 'dependency_labels', models.Label,
                        'test_set'))
        errors = []
        for first_model, first_field, second_model, second_field in model_pairs:
            errors.extend(self._check_invalid_related_objects(
                first_model, first_field, second_model, second_field))

        if errors:
            subject = ('%s relationships to invalid models, cleaned all' %
                       len(errors))
            message = '\n'.join(errors)
            logging.warning(subject)
            logging.warning(message)
            email_manager.manager.enqueue_notify_email(subject, message)


    def _clear_inactive_blocks(self):
        msg = 'Clear out blocks for all completed jobs.'
        logging.info(msg)
        # this would be simpler using NOT IN (subquery), but MySQL
        # treats all IN subqueries as dependent, so this optimizes much
        # better
        self._db.execute("""
            DELETE ihq FROM ineligible_host_queues ihq
            LEFT JOIN (SELECT DISTINCT job_id FROM host_queue_entries
                       WHERE NOT complete) hqe
            USING (job_id) WHERE hqe.job_id IS NULL""")


class TwentyFourHourUpkeep(PeriodicCleanup):
    """Cleanup that runs at the startup of monitor_db and every subsequent
       twenty four hours.
    """


    def __init__(self, db, run_at_initialize=True):
        clean_interval = 24 * 60 # 24 hours
        super(TwentyFourHourUpkeep, self).__init__(
            db, clean_interval, run_at_initialize=run_at_initialize)


    def _cleanup(self):
        logging.info('Running 24 hour clean up')
        self._django_session_cleanup()
        self._check_for_uncleanable_db_inconsistencies()


    def _django_session_cleanup(self):
        """Clean up django_session since django doesn't for us.
           http://www.djangoproject.com/documentation/0.96/sessions/
        """
        logging.info('Deleting old sessions from django_session')
        sql = 'DELETE FROM django_session WHERE expire_date < NOW()'
        self._db.execute(sql)


    def _check_for_uncleanable_db_inconsistencies(self):
        logging.info('Checking for uncleanable DB inconsistencies')
        self._check_for_active_and_complete_queue_entries()
        self._check_for_multiple_platform_hosts()
        self._check_for_no_platform_hosts()
        self._check_for_multiple_atomic_group_hosts()


    def _check_for_active_and_complete_queue_entries(self):
        query = models.HostQueueEntry.objects.filter(active=True, complete=True)
        if query.count() != 0:
            subject = ('%d queue entries found with active=complete=1'
                       % query.count())
            lines = [str(entry.get_object_dict()) for entry in query]
            self._send_inconsistency_message(subject, lines)


    def _check_for_multiple_platform_hosts(self):
        rows = self._db.execute("""
            SELECT hosts.id, hostname, COUNT(1) AS platform_count,
                   GROUP_CONCAT(labels.name)
            FROM hosts
            INNER JOIN hosts_labels ON hosts.id = hosts_labels.host_id
            INNER JOIN labels ON hosts_labels.label_id = labels.id
            WHERE labels.platform
            GROUP BY hosts.id
            HAVING platform_count > 1
            ORDER BY hostname""")
        if rows:
            subject = '%s hosts with multiple platforms' % self._db.rowcount
            lines = [' '.join(str(item) for item in row)
                     for row in rows]
            self._send_inconsistency_message(subject, lines)


    def _check_for_no_platform_hosts(self):
        rows = self._db.execute("""
            SELECT hostname
            FROM hosts
            LEFT JOIN hosts_labels
              ON hosts.id = hosts_labels.host_id
              AND hosts_labels.label_id IN (SELECT id FROM labels
                                            WHERE platform)
            WHERE NOT hosts.invalid AND hosts_labels.host_id IS NULL""")
        if rows:
            subject = '%s hosts with no platform' % self._db.rowcount
            self._send_inconsistency_message(
                subject, [', '.join(row[0] for row in rows)])


    def _check_for_multiple_atomic_group_hosts(self):
        rows = self._db.execute("""
            SELECT hosts.id, hostname, COUNT(DISTINCT atomic_groups.name) AS
                   atomic_group_count, GROUP_CONCAT(labels.name),
                   GROUP_CONCAT(atomic_groups.name)
            FROM hosts
            INNER JOIN hosts_labels ON hosts.id = hosts_labels.host_id
            INNER JOIN labels ON hosts_labels.label_id = labels.id
            INNER JOIN atomic_groups ON
                       labels.atomic_group_id = atomic_groups.id
            WHERE NOT hosts.invalid AND NOT labels.invalid
            GROUP BY hosts.id
            HAVING atomic_group_count > 1
            ORDER BY hostname""")
        if rows:
            subject = '%s hosts with multiple atomic groups' % self._db.rowcount
            lines = [' '.join(str(item) for item in row)
                     for row in rows]
            self._send_inconsistency_message(subject, lines)


    def _send_inconsistency_message(self, subject, lines):
        logging.error(subject)
        message = '\n'.join(lines)
        if len(message) > 5000:
            message = message[:5000] + '\n(truncated)\n'
        email_manager.manager.enqueue_notify_email(subject, message)
