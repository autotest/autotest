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
        logging.info('Checking for db inconsistencies')
        query = models.HostQueueEntry.objects.filter(active=True, complete=True)
        if query.count() != 0:
            subject = ('%d queue entries found with active=complete=1'
                       % query.count())
            message = '\n'.join(str(entry.get_object_dict())
                                for entry in query[:50])
            if len(query) > 50:
                message += '\n(truncated)\n'

            logging.error(subject)
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


    def _django_session_cleanup(self):
        """Clean up django_session since django doesn't for us.
           http://www.djangoproject.com/documentation/0.96/sessions/
        """
        logging.info('Deleting old sessions from django_session')
        sql = 'DELETE FROM django_session WHERE expire_date < NOW()'
        self._db.execute(sql)
