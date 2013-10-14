"""
Database model classes for the scheduler.

Contains model classes abstracting the various DB tables used by the scheduler.
These overlap the Django models in basic functionality, but were written before
the Django models existed and have not yet been phased out.  Some of them
(particularly HostQueueEntry and Job) have considerable scheduler-specific logic
which would probably be ill-suited for inclusion in the general Django model
classes.

Globals:
_notify_email_statuses: list of HQE statuses.  each time a single HQE reaches
        one of these statuses, an email will be sent to the job's email_list.
        comes from settings.
_notify_admin_email_statuses: list of HQE statuses.  each time a single HQE
        reaches one of these statuses, an email will be sent to the grid admin
        email_list. comes from settings.
_grid_admin_email: Autotest grid administrator email (list of emails or mailing
        list). Comes from settings.
_base_url: URL to the local AFE server, used to construct URLs for emails.
_db: DatabaseConnection for this module.
_drone_manager: reference to global DroneManager instance.
"""

import datetime
import itertools
import logging
import os
import re
import sys
import time
import weakref
from autotest.client.shared import host_protections, mail
from autotest.client.shared.settings import settings
from autotest.frontend.afe import models, model_attributes
from autotest.database_legacy import database_connection
from autotest.scheduler import drone_manager
from autotest.scheduler import scheduler_config
from autotest.frontend.afe import reservations

_notify_email_statuses = []
_notify_admin_email_statuses = []
_grid_admin_email = None
_base_url = None

_db = None
_drone_manager = None


def initialize():
    global _db
    _db = database_connection.DatabaseConnection('AUTOTEST_WEB')
    _db.connect(db_type='django')

    notify_statuses_list = settings.get_value("NOTIFICATION",
                                              "notify_email_statuses",
                                              default='')
    global _notify_email_statuses
    _notify_email_statuses = [status for status in
                              re.split(r'[\s,;:]', notify_statuses_list.lower())
                              if status]

    notify_admin_email_statuses_list = settings.get_value("NOTIFICATION",
                                                          "notify_admin_email_statuses",
                                                          default='')
    global _notify_admin_email_statuses
    _notify_admin_email_statuses = [status for status in
                                    re.split(r'[\s,;:]',
                                             notify_admin_email_statuses_list.lower())
                                    if status]

    global _grid_admin_email
    _grid_admin_email = settings.get_value("NOTIFICATION",
                                           "grid_admin_email",
                                           default='')

    # AUTOTEST_WEB.base_url is still a supported config option as some people
    # may wish to override the entire url.
    global _base_url
    config_base_url = settings.get_value(scheduler_config.CONFIG_SECTION,
                                         'base_url', default='')
    if config_base_url:
        _base_url = config_base_url
    else:
        # For the common case of everything running on a single server you
        # can just set the hostname in a single place in the config file.
        server_name = settings.get_value('SERVER', 'hostname')
        if not server_name:
            logging.critical('[SERVER] hostname missing from the config file.')
            sys.exit(1)
        _base_url = 'http://%s/afe/' % server_name

    initialize_globals()


def initialize_globals():
    global _drone_manager
    _drone_manager = drone_manager.instance()


class DelayedCallTask(object):

    """
    A task object like AgentTask for an Agent to run that waits for the
    specified amount of time to have elapsed before calling the supplied
    callback once and finishing.  If the callback returns anything, it is
    assumed to be a new Agent instance and will be added to the dispatcher.

    @attribute end_time: The absolute posix time after which this task will
            call its callback when it is polled and be finished.

    Also has all attributes required by the Agent class.
    """

    def __init__(self, delay_seconds, callback, now_func=None):
        """
        :param delay_seconds: The delay in seconds from now that this task
                will call the supplied callback and be done.
        :param callback: A callable to be called by this task once after at
                least delay_seconds time has elapsed.  It must return None
                or a new Agent instance.
        :param now_func: A time.time like function.  Default: time.time.
                Used for testing.
        """
        assert delay_seconds > 0
        assert callable(callback)
        if not now_func:
            now_func = time.time
        self._now_func = now_func
        self._callback = callback

        self.end_time = self._now_func() + delay_seconds

        # These attributes are required by Agent.
        self.aborted = False
        self.host_ids = ()
        self.success = False
        self.queue_entry_ids = ()
        self.num_processes = 0

    def poll(self):
        if not self.is_done() and self._now_func() >= self.end_time:
            self._callback()
            self.success = True

    def is_done(self):
        return self.success or self.aborted

    def abort(self):
        self.aborted = True


class DBError(Exception):

    """Raised by the DBObject constructor when its select fails."""


class DBObject(object):

    """A miniature object relational model for the database."""

    # Subclasses MUST override these:
    _table_name = ''
    _fields = ()

    # A mapping from (type, id) to the instance of the object for that
    # particular id.  This prevents us from creating new Job() and Host()
    # instances for every HostQueueEntry object that we instantiate as
    # multiple HQEs often share the same Job.
    _instances_by_type_and_id = weakref.WeakValueDictionary()
    _initialized = False

    def __new__(cls, id=None, **kwargs):
        """
        Look to see if we already have an instance for this particular type
        and id.  If so, use it instead of creating a duplicate instance.
        """
        if id is not None:
            instance = cls._instances_by_type_and_id.get((cls, id))
            if instance:
                return instance
        return super(DBObject, cls).__new__(cls, id=id, **kwargs)

    def __init__(self, id=None, row=None, new_record=False, always_query=True):
        assert bool(id) or bool(row)
        if id is not None and row is not None:
            assert id == row[0]
        assert self._table_name, '_table_name must be defined in your class'
        assert self._fields, '_fields must be defined in your class'
        if not new_record:
            if self._initialized and not always_query:
                return  # We've already been initialized.
            if id is None:
                id = row[0]
            # Tell future constructors to use us instead of re-querying while
            # this instance is still around.
            self._instances_by_type_and_id[(type(self), id)] = self

        self.__table = self._table_name

        self.__new_record = new_record

        if row is None:
            row = self._fetch_row_from_db(id)

        if self._initialized:
            differences = self._compare_fields_in_row(row)
            if differences:
                logging.warn(
                    'initialized %s %s instance requery is updating: %s',
                    type(self), self.id, differences)
        self._update_fields_from_row(row)
        self._initialized = True

    @classmethod
    def _clear_instance_cache(cls):
        """Used for testing, clear the internal instance cache."""
        cls._instances_by_type_and_id.clear()

    def _fetch_row_from_db(self, row_id):
        """
        Fetch a row from the db representing a model

        Only fetch columns specified in the fileds of the model

        :param row_id: the numeric value of the `ID` column of the table
        :type row_id: integer
        :returns: the row whose `ID` column is row_id
        """
        fields = ", ".join(self._fields)
        sql = 'SELECT %s FROM %s WHERE ID=%%s' % (fields, self.__table)
        rows = _db.execute(sql, (row_id,))
        if not rows:
            raise DBError("row not found (table=%s, row id=%s)"
                          % (self.__table, row_id))
        return rows[0]

    def _assert_row_length(self, row):
        assert len(row) == len(self._fields), (
            "table = %s, row = %s/%d, fields = %s/%d" % (
                self.__table, row, len(row), self._fields, len(self._fields)))

    def _compare_fields_in_row(self, row):
        """
        Given a row as returned by a SELECT query, compare it to our existing in
        memory fields.  Fractional seconds are stripped from datetime values
        before comparison.

        :param row - A sequence of values corresponding to fields named in
                The class attribute _fields.

        :return: A dictionary listing the differences keyed by field name
                containing tuples of (current_value, row_value).
        """
        self._assert_row_length(row)
        differences = {}
        datetime_cmp_fmt = '%Y-%m-%d %H:%M:%S'  # Leave off the microseconds.
        for field, row_value in itertools.izip(self._fields, row):
            current_value = getattr(self, field)
            if (isinstance(current_value, datetime.datetime)
                    and isinstance(row_value, datetime.datetime)):
                current_value = current_value.strftime(datetime_cmp_fmt)
                row_value = row_value.strftime(datetime_cmp_fmt)
            if current_value != row_value:
                differences[field] = (current_value, row_value)
        return differences

    def _update_fields_from_row(self, row):
        """
        Update our field attributes using a single row returned by SELECT.

        :param row - A sequence of values corresponding to fields named in
                the class fields list.
        """
        self._assert_row_length(row)

        self._valid_fields = set()
        for field, value in itertools.izip(self._fields, row):
            setattr(self, field, value)
            self._valid_fields.add(field)

        self._valid_fields.remove('id')

    def update_from_database(self):
        assert self.id is not None
        row = self._fetch_row_from_db(self.id)
        self._update_fields_from_row(row)

    def count(self, where, table=None):
        if not table:
            table = self.__table

        rows = _db.execute("""
                SELECT count(*) FROM %s
                WHERE %s
        """ % (table, where))

        assert len(rows) == 1

        return int(rows[0][0])

    def update_field(self, field, value):
        assert field in self._valid_fields

        if getattr(self, field) == value:
            return

        query = "UPDATE %s SET %s = %%s WHERE id = %%s" % (self.__table, field)
        _db.execute(query, (value, self.id))

        setattr(self, field, value)

    def save(self):
        if self.__new_record:
            keys = self._fields[1:]  # avoid id
            columns = ','.join([str(key) for key in keys])
            values = []
            for key in keys:
                value = getattr(self, key)
                if value is None:
                    values.append('NULL')
                else:
                    values.append('"%s"' % value)
            values_str = ','.join(values)
            query = ('INSERT INTO %s (%s) VALUES (%s)' %
                     (self.__table, columns, values_str))
            _db.execute(query)
            # Update our id to the one the database just assigned to us.
            self.id = _db.execute('SELECT LAST_INSERT_ID()')[0][0]

    def delete(self):
        self._instances_by_type_and_id.pop((type(self), id), None)
        self._initialized = False
        self._valid_fields.clear()
        query = 'DELETE FROM %s WHERE id=%%s' % self.__table
        _db.execute(query, (self.id,))

    @staticmethod
    def _prefix_with(string, prefix):
        if string:
            string = prefix + string
        return string

    @classmethod
    def fetch(cls, where='', params=(), joins='', order_by=''):
        """
        Construct instances of our class based on the given database query.

        @yields One class instance for each row fetched.
        """
        order_by = cls._prefix_with(order_by, 'ORDER BY ')
        where = cls._prefix_with(where, 'WHERE ')
        # construct field names table.field for all fields in a class
        fields = [cls._table_name + '.' + f for f in cls._fields]
        query = ('SELECT %(fields)s FROM %(table)s %(joins)s '
                 '%(where)s %(order_by)s' % {'fields': ", ".join(fields),
                                             'table': cls._table_name,
                                             'joins': joins,
                                             'where': where,
                                             'order_by': order_by})
        rows = _db.execute(query, params)
        return [cls(id=row[0], row=row) for row in rows]


class IneligibleHostQueue(DBObject):
    _table_name = 'afe_ineligible_host_queues'
    _fields = ('id', 'job_id', 'host_id')


class AtomicGroup(DBObject):
    _table_name = 'afe_atomic_groups'
    _fields = ('id', 'name', 'description', 'max_number_of_machines',
               'invalid')


class Label(DBObject):
    _table_name = 'afe_labels'
    _fields = ('id', 'name', 'kernel_config', 'platform', 'invalid',
               'only_if_needed', 'atomic_group_id')

    def __repr__(self):
        return 'Label(name=%r, id=%d, atomic_group_id=%r)' % (
            self.name, self.id, self.atomic_group_id)


class Host(DBObject):
    _table_name = 'afe_hosts'
    _fields = ('id', 'hostname', 'locked', 'synch_id', 'status',
               'invalid', 'protection', 'locked_by_id', 'lock_time', 'dirty')

    def set_status(self, status):
        logging.info('%s -> %s', self.hostname, status)
        self.update_field('status', status)

    def platform_and_labels(self):
        """
        Returns a tuple (platform_name, list_of_all_label_names).
        """
        rows = _db.execute("""
                SELECT afe_labels.name, afe_labels.platform
                FROM afe_labels
                INNER JOIN afe_hosts_labels ON
                        afe_labels.id = afe_hosts_labels.label_id
                WHERE afe_hosts_labels.host_id = %s
                ORDER BY afe_labels.name
                """, (self.id,))
        platform = None
        all_labels = []
        for label_name, is_platform in rows:
            if is_platform:
                platform = label_name
            all_labels.append(label_name)
        return platform, all_labels

    _ALPHANUM_HOST_RE = re.compile(r'^([a-z-]+)(\d+)$', re.IGNORECASE)

    @classmethod
    def cmp_for_sort(cls, a, b):
        """
        A comparison function for sorting Host objects by hostname.

        This strips any trailing numeric digits, ignores leading 0s and
        compares hostnames by the leading name and the trailing digits as a
        number.  If both hostnames do not match this pattern, they are simply
        compared as lower case strings.

        Example of how hostnames will be sorted:

          alice, host1, host2, host09, host010, host10, host11, yolkfolk

        This hopefully satisfy most people's hostname sorting needs regardless
        of their exact naming schemes.  Nobody sane should have both a host10
        and host010 (but the algorithm works regardless).
        """
        lower_a = a.hostname.lower()
        lower_b = b.hostname.lower()
        match_a = cls._ALPHANUM_HOST_RE.match(lower_a)
        match_b = cls._ALPHANUM_HOST_RE.match(lower_b)
        if match_a and match_b:
            name_a, number_a_str = match_a.groups()
            name_b, number_b_str = match_b.groups()
            number_a = int(number_a_str.lstrip('0'))
            number_b = int(number_b_str.lstrip('0'))
            result = cmp((name_a, number_a), (name_b, number_b))
            if result == 0 and lower_a != lower_b:
                # If they compared equal above but the lower case names are
                # indeed different, don't report equality.  abc012 != abc12.
                return cmp(lower_a, lower_b)
            return result
        else:
            return cmp(lower_a, lower_b)


class HostQueueEntry(DBObject):
    _table_name = 'afe_host_queue_entries'
    _fields = ('id', 'job_id', 'host_id', 'profile', 'status', 'meta_host',
               'active', 'complete', 'deleted', 'execution_subdir',
               'atomic_group_id', 'aborted', 'started_on')

    def __init__(self, id=None, row=None, **kwargs):
        assert id or row
        super(HostQueueEntry, self).__init__(id=id, row=row, **kwargs)
        self.job = Job(self.job_id)

        if self.host_id:
            self.host = Host(self.host_id)
        else:
            self.host = None

        if self.atomic_group_id:
            self.atomic_group = AtomicGroup(self.atomic_group_id,
                                            always_query=False)
        else:
            self.atomic_group = None

        self.queue_log_path = os.path.join(self.job.tag(),
                                           'queue.log.' + str(self.id))

    @classmethod
    def clone(cls, template):
        """
        Creates a new row using the values from a template instance.

        The new instance will not exist in the database or have a valid
        id attribute until its save() method is called.
        """
        assert isinstance(template, cls)
        new_row = [getattr(template, field) for field in cls._fields]
        clone = cls(row=new_row, new_record=True)
        clone.id = None
        return clone

    def _view_job_url(self):
        return "%s#tab_id=view_job&object_id=%s" % (_base_url, self.job.id)

    def get_labels(self):
        """
        Get all labels associated with this host queue entry (either via the
        meta_host or as a job dependency label).  The labels yielded are not
        guaranteed to be unique.

        @yields Label instances associated with this host_queue_entry.
        """
        if self.meta_host:
            yield Label(id=self.meta_host, always_query=False)
        labels = Label.fetch(
            joins="JOIN afe_jobs_dependency_labels AS deps "
            "ON (afe_labels.id = deps.label_id)",
            where="deps.job_id = %d" % self.job.id)
        for label in labels:
            yield label

    def set_host(self, host):
        if host:
            logging.info('Assigning host %s to entry %s', host.hostname, self)
            self.queue_log_record('Assigning host ' + host.hostname)
            self.update_field('host_id', host.id)
            self.block_host(host.id)
        else:
            logging.info('Releasing host from %s', self)
            self.queue_log_record('Releasing host')
            self.unblock_host(self.host.id)
            self.update_field('host_id', None)

        self.host = host

    def queue_log_record(self, log_line):
        now = str(datetime.datetime.now())
        _drone_manager.write_lines_to_file(self.queue_log_path,
                                           [now + ' ' + log_line])

    def block_host(self, host_id):
        logging.info("creating block %s/%s", self.job.id, host_id)
        row = [0, self.job.id, host_id]
        block = IneligibleHostQueue(row=row, new_record=True)
        block.save()

    def unblock_host(self, host_id):
        logging.info("removing block %s/%s", self.job.id, host_id)
        blocks = IneligibleHostQueue.fetch(
            'job_id=%d and host_id=%d' % (self.job.id, host_id))
        for block in blocks:
            block.delete()

    def set_execution_subdir(self, subdir=None):
        if subdir is None:
            assert self.host
            subdir = self.host.hostname
        self.update_field('execution_subdir', subdir)

    def _get_hostname(self):
        if self.host:
            return self.host.hostname
        return 'no host'

    def __str__(self):
        flags = []
        if self.active:
            flags.append('active')
        if self.complete:
            flags.append('complete')
        if self.deleted:
            flags.append('deleted')
        if self.aborted:
            flags.append('aborted')
        flags_str = ','.join(flags)
        if flags_str:
            flags_str = ' [%s]' % flags_str
        return "%s/%d (%d) %s%s" % (self._get_hostname(), self.job.id, self.id,
                                    self.status, flags_str)

    def set_status(self, status):
        logging.info("%s -> %s", self, status)

        self.update_field('status', status)

        active = (status in models.HostQueueEntry.ACTIVE_STATUSES)
        complete = (status in models.HostQueueEntry.COMPLETE_STATUSES)
        assert not (active and complete)

        self.update_field('active', active)
        self.update_field('complete', complete)

        should_email_status = (status.lower() in _notify_email_statuses or
                               'all' in _notify_email_statuses)

        should_email_admin_status = (status.lower() in
                                     _notify_admin_email_statuses or
                                     'all' in _notify_admin_email_statuses)

        if complete:
            self._on_complete(status)
            self._email_on_job_complete(should_email_admin_status)

        if should_email_status:
            self._email_on_status(status)

        if should_email_admin_status:
            self._email_admin_on_status(status)

    def _on_complete(self, status):
        if status is not models.HostQueueEntry.Status.ABORTED:
            self.job.stop_if_necessary()

        if not self.execution_subdir:
            return
        # unregister any possible pidfiles associated with this queue entry
        for pidfile_name in drone_manager.ALL_PIDFILE_NAMES:
            pidfile_id = _drone_manager.get_pidfile_id_from(
                self.execution_path(), pidfile_name=pidfile_name)
            _drone_manager.unregister_pidfile(pidfile_id)

    def _get_status_email_contents(self, status, summary=None, hostname=None):
        """
        Gather info for the status notification e-mails.

        If needed, we could start using the Django templating engine to create
        the subject and the e-mail body, but that doesn't seem necessary right
        now.

        :param status: Job status text. Mandatory.
        :param summary: Job summary text. Optional.
        :param hostname: A hostname for the job. Optional.

        :return: Tuple (subject, body) for the notification e-mail.
        """
        job_stats = Job(id=self.job.id).get_execution_details()

        subject = 'Autotest #%s' % self.job.id

        if hostname is not None:
            subject += ' | %s on %s' % (self.job.name, hostname)
        else:
            subject += ' | %s' % self.job.name

        status = status.split()[-1]
        if status == "Completed":
            subject += ' | success: %.2f%%' % job_stats['success_rate']
        else:
            subject += ' | %s' % status

        body = ""
        if int(job_stats['total_executed']) > 0:
            body += ("run: %s | pass: %s | skip: %s | fail: %s" %
                     (job_stats['total_executed'], job_stats['total_passed'],
                      job_stats['total_skipped'], job_stats['total_failed']))
            e_time = job_stats['execution_time']
            if e_time not in ['(could not determine)', '(none)']:
                body += " | runtime: %s" % e_time
            if status == "Completed":
                body += " | success: %.2f%%" % job_stats['success_rate']
            else:
                body += "\n[Warning] Job status: %s" % status

            body += "\n%s\n\n" % self._view_job_url()

        body += job_stats['fail_detail']
        body += job_stats['warn_detail']
        body += job_stats['skip_detail']
        body += job_stats['pass_detail']

        keyval_list = job_stats['keyval_dict_list']
        if keyval_list:
            for kv in keyval_list:
                k, v = kv.items()[0]
                body += "%s:\n" % k
                for part in v.split():
                    body += "  %s\n" % part
                body += "\n"

        if hostname is not None:
            body += "Job was run on host %s\n" % hostname

        body += ("For more details, check the full report on the web:\n%s\n" %
                 self._view_job_url())

        return subject, body

    def _email_on_status(self, status):
        hostname = self._get_hostname()
        subject, body = self._get_status_email_contents(status, None, hostname)
        mail.manager.send(self.job.email_list, subject, body)

    def _email_admin_on_status(self, status):
        hostname = self._get_hostname()
        subject, body = self._get_status_email_contents(status, None, hostname)
        mail.manager.send(_grid_admin_email, subject, body)

    def _email_on_job_complete(self, email_admin=False):
        if not self.job.is_finished():
            return

        summary = []
        hosts_queue = HostQueueEntry.fetch('job_id = %s' % self.job.id)
        for queue_entry in hosts_queue:
            summary.append("Host: %s Status: %s" %
                          (queue_entry._get_hostname(),
                           queue_entry.status))

        summary = "\n".join(summary)
        status_counts = models.Job.objects.get_status_counts(
            [self.job.id])[self.job.id]
        status = ', '.join('%d %s' % (count, status) for status, count
                           in status_counts.iteritems())

        subject, body = self._get_status_email_contents(status, summary, None)

        if email_admin:
            mail.manager.send(_grid_admin_email, subject, body)
        else:
            mail.manager.send(self.job.email_list, subject, body)

    def schedule_pre_job_tasks(self):
        logging.info("%s/%s/%s (job %s, entry %s) scheduled on %s, status=%s",
                     self.job.name, self.meta_host, self.atomic_group_id,
                     self.job.id, self.id, self.host.hostname, self.status)
        # just before doing any actual work reserve the host if requested
        if self.job.reserve_hosts:
            logging.info("Job %s, reserving %s for %s",
                         self.job.id, self.host.hostname, self.job.owner)
            reservations.create([self.host.hostname], self.job.owner)
        self._do_schedule_pre_job_tasks()

    def _do_schedule_pre_job_tasks(self):
        # Every host goes thru the Verifying stage (which may or may not
        # actually do anything as determined by get_pre_job_tasks).
        self.set_status(models.HostQueueEntry.Status.VERIFYING)
        self.job.schedule_pre_job_tasks(queue_entry=self)

    def requeue(self):
        assert self.host
        self.set_status(models.HostQueueEntry.Status.QUEUED)
        self.update_field('started_on', None)
        # verify/cleanup failure sets the execution subdir, so reset it here
        self.set_execution_subdir('')
        if self.meta_host:
            self.set_host(None)

    @property
    def aborted_by(self):
        self._load_abort_info()
        return self._aborted_by

    @property
    def aborted_on(self):
        self._load_abort_info()
        return self._aborted_on

    def _load_abort_info(self):
        """ Fetch info about who aborted the job. """
        if hasattr(self, "_aborted_by"):
            return
        rows = _db.execute("""
                SELECT afe_users.login,
                        afe_aborted_host_queue_entries.aborted_on
                FROM afe_aborted_host_queue_entries
                INNER JOIN afe_users
                ON afe_users.id = afe_aborted_host_queue_entries.aborted_by_id
                WHERE afe_aborted_host_queue_entries.queue_entry_id = %s
                """, (self.id,))
        if rows:
            self._aborted_by, self._aborted_on = rows[0]
        else:
            self._aborted_by = self._aborted_on = None

    def on_pending(self):
        """
        Called when an entry in a synchronous job has passed verify.  If the
        job is ready to run, sets the entries to STARTING. Otherwise, it leaves
        them in PENDING.
        """
        self.set_status(models.HostQueueEntry.Status.PENDING)
        self.host.set_status(models.Host.Status.PENDING)

        # Some debug code here: sends an email if an asynchronous job does not
        # immediately enter Starting.
        # TODO: Remove this once we figure out why asynchronous jobs are getting
        # stuck in Pending.
        self.job.run_if_ready(queue_entry=self)
        if (self.job.synch_count == 1 and
                self.status == models.HostQueueEntry.Status.PENDING):
            subject = 'Job %s (id %s)' % (self.job.name, self.job.id)
            message = 'Asynchronous job stuck in Pending'
            mail.manager.enqueue_admin(subject, message)

    def abort(self, dispatcher):
        assert self.aborted and not self.complete

        Status = models.HostQueueEntry.Status
        if self.status in (Status.GATHERING, Status.PARSING, Status.ARCHIVING):
            # do nothing; post-job tasks will finish and then mark this entry
            # with status "Aborted" and take care of the host
            return

        if self.status in (Status.STARTING, Status.PENDING, Status.RUNNING,
                           Status.WAITING):
            assert not dispatcher.get_agents_for_entry(self)
            self.host.set_status(models.Host.Status.READY)
        elif self.status == Status.VERIFYING:
            models.SpecialTask.objects.create(
                task=models.SpecialTask.Task.CLEANUP,
                host=models.Host.objects.get(id=self.host.id),
                requested_by=self.job.owner_model())

        self.set_status(Status.ABORTED)
        self.job.abort_delay_ready_task()

    def get_group_name(self):
        atomic_group = self.atomic_group
        if not atomic_group:
            return ''

        # Look at any meta_host and dependency labels and pick the first
        # one that also specifies this atomic group.  Use that label name
        # as the group name if possible (it is more specific).
        for label in self.get_labels():
            if label.atomic_group_id:
                assert label.atomic_group_id == atomic_group.id
                return label.name
        return atomic_group.name

    def execution_tag(self):
        assert self.execution_subdir
        return "%s/%s" % (self.job.tag(), self.execution_subdir)

    def execution_path(self):
        return self.execution_tag()

    def set_started_on_now(self):
        self.update_field('started_on', datetime.datetime.now())

    def is_hostless(self):
        return (self.host_id is None
                and self.meta_host is None
                and self.atomic_group_id is None)


class Job(DBObject):
    _table_name = 'afe_jobs'
    _fields = ('id', 'owner', 'name', 'priority', 'control_file',
               'control_type', 'created_on', 'synch_count', 'timeout',
               'run_verify', 'email_list', 'reboot_before', 'reboot_after',
               'parse_failed_repair', 'max_runtime_hrs', 'drone_set_id',
               'parameterized_job_id', 'reserve_hosts')
    # This does not need to be a column in the DB.  The delays are likely to
    # be configured short.  If the scheduler is stopped and restarted in
    # the middle of a job's delay cycle, the delay cycle will either be
    # repeated or skipped depending on the number of Pending machines found
    # when the restarted scheduler recovers to track it.  Not a problem.
    #
    # A reference to the DelayedCallTask that will wake up the job should
    # no other HQEs change state in time.  Its end_time attribute is used
    # by our run_with_ready_delay() method to determine if the wait is over.
    _delay_ready_task = None

    # TODO(gps): On scheduler start/recovery we need to call HQE.on_pending() on
    # all status='Pending' atomic group HQEs incase a delay was running when the
    # scheduler was restarted and no more hosts ever successfully exit Verify.

    def __init__(self, id=None, row=None, **kwargs):
        assert id or row
        super(Job, self).__init__(id=id, row=row, **kwargs)
        self._owner_model = None  # caches model instance of owner

    def model(self):
        return models.Job.objects.get(id=self.id)

    def owner_model(self):
        # work around the fact that the Job owner field is a string, not a
        # foreign key
        if not self._owner_model:
            self._owner_model = models.User.objects.get(login=self.owner)
        return self._owner_model

    def is_server_job(self):
        return self.control_type != 2

    def tag(self):
        return "%s-%s" % (self.id, self.owner)

    def get_host_queue_entries(self):
        rows = _db.execute("""
                SELECT * FROM afe_host_queue_entries
                WHERE job_id= %s
        """, (self.id,))
        entries = [HostQueueEntry(row=i) for i in rows]

        assert len(entries) > 0

        return entries

    def get_execution_details(self):
        """
        Get test execution details for this job.

        :return: Dictionary with test execution details
        """
        def _find_framework_tests(rows):
            """
            Here we are looking for tests such as SERVER_JOB and CLIENT_JOB.*
            Those are autotest 'internal job' tests, so they should not be
            counted when evaluating the test stats.

            :param rows: List of rows (matrix) with database results.
            """
            job_test_pattern = re.compile('SERVER|CLIENT\\_JOB\.[\d]')
            test_jobs = []
            for r in rows:
                test_name = r[0]
                if job_test_pattern.match(test_name):
                    test_jobs.append(test_name)

            return test_jobs

        def _format_rows(rows, max_length=75):
            """
            Format failure rows, so they are legible on the resulting email.

            :param rows: List of rows (matrix) with database results.
            :param field: Field of the stats dict we want to fill.
            :param max_length: Int with maximum length of a line printed.
            """
            formatted_row = ""
            status_translate = {"GOOD": "PASS", "TEST_NA": "SKIP"}
            if rows:
                label = rows[0][1]
                if label in status_translate.keys():
                    label = status_translate[label]
                formatted_row += "%s (%s):\n" % (label, len(rows))
                for row in rows:
                    # Add test name, status and count
                    formatted_row += "  %s\n" % (row[0])
                    # start to add reasons
                    if row[2]:
                        reason = row[2].split()
                        curr_length = 0
                        formatted_row += "    "
                        for word in reason:
                            previous_length = curr_length
                            curr_length += len(word)
                            if curr_length > max_length:
                                curr_length = 0
                                if previous_length != 0:
                                    formatted_row += "\n    %s " % word
                                else:
                                    # Corner case, len(word) > 75 char
                                    formatted_row += "%s\n    " % word
                            else:
                                formatted_row += "%s " % word
                        formatted_row += "\n"
                formatted_row += "\n"
            return formatted_row

        def _get_test_keyval(jobid, keyname, db, default=''):
            try:
                lines = []
                idx = db.execute('SELECT job_idx FROM tko_jobs WHERE '
                                 'afe_job_id=%s' % jobid)[0]
                test_indexes = db.execute('SELECT test_idx FROM tko_tests WHERE '
                                          'job_idx=%s' % idx)
                for i in test_indexes:
                    rows = db.execute('SELECT value FROM tko_test_attributes '
                                      'WHERE test_idx=%s AND attribute="%s"' %
                                     (i[0], keyname))
                    if rows:
                        for row in rows:
                            line = []
                            for c in row:
                                line.append(str(c))
                            lines.append(" ".join(line))
                if lines:
                    return lines[0]
                else:
                    return default
            except:
                return default

        stats = {}

        rows = _db.execute("""
                SELECT t.test, s.word, t.reason
                FROM tko_tests AS t, tko_jobs AS j, tko_status AS s
                WHERE t.job_idx = j.job_idx
                AND s.status_idx = t.status
                AND j.afe_job_id = %s
                """ % self.id)

        framework_tests = _find_framework_tests(rows)
        failed_rows = [r for r in rows if r[1] != 'GOOD']
        framework_tests_failed = _find_framework_tests(failed_rows)
        explicitly_failed_rows = [r for r in rows if r[1] == 'FAIL']
        warn_rows = [r for r in rows if r[1] == 'WARN']
        skipped_rows = [(r[0], r[1], '') for r in rows if r[1] == 'TEST_NA']
        passed_rows = [(r[0], r[1], '') for r in rows if r[1] == 'GOOD' and r[0] not in framework_tests]

        total_executed = len(rows) - len(framework_tests)
        total_failed = len(failed_rows) - len(framework_tests_failed)
        total_skipped = len(skipped_rows)

        if total_executed > 0:
            success_rate = 100 - ((total_failed / float(total_executed)) * 100)
        else:
            success_rate = 0

        stats['total_executed'] = total_executed
        stats['total_failed'] = total_failed
        stats['total_passed'] = total_executed - total_failed
        stats['total_skipped'] = total_skipped
        stats['success_rate'] = success_rate

        stats['fail_detail'] = _format_rows(explicitly_failed_rows)
        stats['warn_detail'] = _format_rows(warn_rows)
        stats['skip_detail'] = _format_rows(skipped_rows)
        stats['pass_detail'] = _format_rows(passed_rows)

        time_row = _db.execute("""
                   SELECT started_time, finished_time
                   FROM tko_jobs
                   WHERE afe_job_id = %s
                   """ % self.id)

        if time_row:
            t_begin, t_end = time_row[0]
            try:
                delta = t_end - t_begin
                minutes, seconds = divmod(delta.seconds, 60)
                hours, minutes = divmod(minutes, 60)
                stats['execution_time'] = ("%02d:%02d:%02d" %
                                           (hours, minutes, seconds))
            # One of t_end or t_begin are None
            except TypeError:
                stats['execution_time'] = '(could not determine)'
        else:
            stats['execution_time'] = '(none)'

        keyval_dict_list = []
        keyval_list = self.get_keyval_list()
        print "DBG: kv list obtained from get_keyval_list: %s" % keyval_list
        if keyval_list:
            for kv in keyval_list:
                keyval_dict = {}
                keyval_dict[kv] = _get_test_keyval(self.id, kv, _db)
                keyval_dict_list.append(keyval_dict)
        stats['keyval_dict_list'] = keyval_dict_list

        return stats

    def get_keyval_list(self):
        raw = settings.get_value('SCHEDULER',
                                 'keyval_names_exibit_summary_mail',
                                 default="")
        keyval_list = re.split(r'[\s,;:]', raw)
        return [element for element in keyval_list if element]

    def set_status(self, status, update_queues=False):
        self.update_field('status', status)

        if update_queues:
            for queue_entry in self.get_host_queue_entries():
                queue_entry.set_status(status)

    def keyval_dict(self):
        return self.model().keyval_dict()

    def _atomic_and_has_started(self):
        """
        :return: True if any of the HostQueueEntries associated with this job
        have entered the Status.STARTING state or beyond.
        """
        atomic_entries = models.HostQueueEntry.objects.filter(
            job=self.id, atomic_group__isnull=False)
        if atomic_entries.count() <= 0:
            return False

        # These states may *only* be reached if Job.run() has been called.
        started_statuses = (models.HostQueueEntry.Status.STARTING,
                            models.HostQueueEntry.Status.RUNNING,
                            models.HostQueueEntry.Status.COMPLETED)

        started_entries = atomic_entries.filter(status__in=started_statuses)
        return started_entries.count() > 0

    def _hosts_assigned_count(self):
        """The number of HostQueueEntries assigned a Host for this job."""
        entries = models.HostQueueEntry.objects.filter(job=self.id,
                                                       host__isnull=False)
        return entries.count()

    def _pending_count(self):
        """The number of HostQueueEntries for this job in the Pending state."""
        pending_entries = models.HostQueueEntry.objects.filter(
            job=self.id, status=models.HostQueueEntry.Status.PENDING)
        return pending_entries.count()

    def _max_hosts_needed_to_run(self, atomic_group):
        """
        :param atomic_group: The AtomicGroup associated with this job that we
                are using to set an upper bound on the threshold.
        :return: The maximum number of HostQueueEntries assigned a Host before
                this job can run.
        """
        return min(self._hosts_assigned_count(),
                   atomic_group.max_number_of_machines)

    def _min_hosts_needed_to_run(self):
        """Return the minimum number of hosts needed to run this job."""
        return self.synch_count

    def is_ready(self):
        # NOTE: Atomic group jobs stop reporting ready after they have been
        # started to avoid launching multiple copies of one atomic job.
        # Only possible if synch_count is less than than half the number of
        # machines in the atomic group.
        pending_count = self._pending_count()
        atomic_and_has_started = self._atomic_and_has_started()
        ready = (pending_count >= self.synch_count
                 and not atomic_and_has_started)

        if not ready:
            logging.info(
                'Job %s not ready: %s pending, %s required '
                '(Atomic and started: %s)',
                self, pending_count, self.synch_count,
                atomic_and_has_started)

        return ready

    def num_machines(self, clause=None):
        sql = "job_id=%s" % self.id
        if clause:
            sql += " AND (%s)" % clause
        return self.count(sql, table='afe_host_queue_entries')

    def num_queued(self):
        return self.num_machines('not complete')

    def num_active(self):
        return self.num_machines('active')

    def num_complete(self):
        return self.num_machines('complete')

    def is_finished(self):
        return self.num_complete() == self.num_machines()

    def _not_yet_run_entries(self, include_verifying=True):
        statuses = [models.HostQueueEntry.Status.QUEUED,
                    models.HostQueueEntry.Status.PENDING]
        if include_verifying:
            statuses.append(models.HostQueueEntry.Status.VERIFYING)
        return models.HostQueueEntry.objects.filter(job=self.id,
                                                    status__in=statuses)

    def _stop_all_entries(self):
        entries_to_stop = self._not_yet_run_entries(
            include_verifying=False)
        for child_entry in entries_to_stop:
            assert not child_entry.complete, (
                '%s status=%s, active=%s, complete=%s' %
                (child_entry.id, child_entry.status, child_entry.active,
                 child_entry.complete))
            if child_entry.status == models.HostQueueEntry.Status.PENDING:
                child_entry.host.status = models.Host.Status.READY
                child_entry.host.save()
            child_entry.status = models.HostQueueEntry.Status.STOPPED
            child_entry.save()

    def stop_if_necessary(self):
        not_yet_run = self._not_yet_run_entries()
        if not_yet_run.count() < self.synch_count:
            self._stop_all_entries()

    def write_to_machines_file(self, queue_entry):
        hostname = queue_entry.host.hostname
        file_path = os.path.join(self.tag(), '.machines')
        _drone_manager.write_lines_to_file(file_path, [hostname])

    def _next_group_name(self, group_name=''):
        """:return: a directory name to use for the next host group results."""
        if group_name:
            # Sanitize for use as a pathname.
            group_name = group_name.replace(os.path.sep, '_')
            if group_name.startswith('.'):
                group_name = '_' + group_name[1:]
            # Add a separator between the group name and 'group%d'.
            group_name += '.'
        group_count_re = re.compile(r'%sgroup(\d+)' % re.escape(group_name))
        query = models.HostQueueEntry.objects.filter(
            job=self.id).values('execution_subdir').distinct()
        subdirs = (entry['execution_subdir'] for entry in query)
        group_matches = (group_count_re.match(subdir) for subdir in subdirs)
        ids = [int(match.group(1)) for match in group_matches if match]
        if ids:
            next_id = max(ids) + 1
        else:
            next_id = 0
        return '%sgroup%d' % (group_name, next_id)

    def get_group_entries(self, queue_entry_from_group):
        """
        :param queue_entry_from_group: A HostQueueEntry instance to find other
                group entries on this job for.

        :return: A list of HostQueueEntry objects all executing this job as
                part of the same group as the one supplied (having the same
                execution_subdir).
        """
        execution_subdir = queue_entry_from_group.execution_subdir
        return list(HostQueueEntry.fetch(
            where='job_id=%s AND execution_subdir=%s',
            params=(self.id, execution_subdir)))

    def _should_run_cleanup(self, queue_entry):
        if self.reboot_before == model_attributes.RebootBefore.ALWAYS:
            return True
        elif self.reboot_before == model_attributes.RebootBefore.IF_DIRTY:
            return queue_entry.host.dirty
        return False

    def _should_run_verify(self, queue_entry):
        do_not_verify = (queue_entry.host.protection ==
                         host_protections.Protection.DO_NOT_VERIFY)
        if do_not_verify:
            return False
        return self.run_verify

    def schedule_pre_job_tasks(self, queue_entry):
        """
        Get a list of tasks to perform before the host_queue_entry
        may be used to run this Job (such as Cleanup & Verify).

        :return: A list of tasks to be done to the given queue_entry before
                it should be considered be ready to run this job.  The last
                task in the list calls HostQueueEntry.on_pending(), which
                continues the flow of the job.
        """
        if self._should_run_cleanup(queue_entry):
            task = models.SpecialTask.Task.CLEANUP
        elif self._should_run_verify(queue_entry):
            task = models.SpecialTask.Task.VERIFY
        else:
            queue_entry.on_pending()
            return

        queue_entry = models.HostQueueEntry.objects.get(id=queue_entry.id)
        models.SpecialTask.objects.create(
            host=models.Host.objects.get(id=queue_entry.host_id),
            queue_entry=queue_entry, task=task)

    def _assign_new_group(self, queue_entries, group_name=''):
        if len(queue_entries) == 1:
            group_subdir_name = queue_entries[0].host.hostname
        else:
            group_subdir_name = self._next_group_name(group_name)
            logging.info('Running synchronous job %d hosts %s as %s',
                         self.id, [entry.host.hostname for entry in queue_entries],
                         group_subdir_name)

        for queue_entry in queue_entries:
            queue_entry.set_execution_subdir(group_subdir_name)

    def _choose_group_to_run(self, include_queue_entry):
        """
        :return: A tuple containing a list of HostQueueEntry instances to be
                used to run this Job, a string group name to suggest giving
                to this job in the results database.
        """
        atomic_group = include_queue_entry.atomic_group
        chosen_entries = [include_queue_entry]
        if atomic_group:
            num_entries_wanted = atomic_group.max_number_of_machines
        else:
            num_entries_wanted = self.synch_count
        num_entries_wanted -= len(chosen_entries)

        if num_entries_wanted > 0:
            where_clause = 'job_id = %s AND status = "Pending" AND id != %s'
            pending_entries = list(HostQueueEntry.fetch(
                                   where=where_clause,
                                   params=(self.id, include_queue_entry.id)))

            # Sort the chosen hosts by hostname before slicing.
            def cmp_queue_entries_by_hostname(entry_a, entry_b):
                return Host.cmp_for_sort(entry_a.host, entry_b.host)
            pending_entries.sort(cmp=cmp_queue_entries_by_hostname)
            chosen_entries += pending_entries[:num_entries_wanted]

        # Sanity check.  We'll only ever be called if this can be met.
        if len(chosen_entries) < self.synch_count:
            subject = 'Job not started, too few chosen entries'
            message = ('job %s got less than %s chosen entries: %s' % (
                self.id, self.synch_count, chosen_entries))
            logging.error(message)
            mail.manager.enqueue_admin(subject, message)
            return []

        group_name = include_queue_entry.get_group_name()

        self._assign_new_group(chosen_entries, group_name=group_name)
        return chosen_entries

    def run_if_ready(self, queue_entry):
        """
        Run this job by kicking its HQEs into status='Starting' if enough
        hosts are ready for it to run.

        Cleans up by kicking HQEs into status='Stopped' if this Job is not
        ready to run.
        """
        if not self.is_ready():
            self.stop_if_necessary()
        elif queue_entry.atomic_group:
            self.run_with_ready_delay(queue_entry)
        else:
            self.run(queue_entry)

    def run_with_ready_delay(self, queue_entry):
        """
        Start a delay to wait for more hosts to enter Pending state before
        launching an atomic group job.  Once set, the a delay cannot be reset.

        :param queue_entry: The HostQueueEntry object to get atomic group
                info from and pass to run_if_ready when the delay is up.

        :return: An Agent to run the job as appropriate or None if a delay
                has already been set.
        """
        assert queue_entry.job_id == self.id
        assert queue_entry.atomic_group
        delay = scheduler_config.config.secs_to_wait_for_atomic_group_hosts
        over_max_threshold = (self._pending_count() >=
                              self._max_hosts_needed_to_run(queue_entry.atomic_group))
        delay_expired = (self._delay_ready_task and
                         time.time() >= self._delay_ready_task.end_time)

        # Delay is disabled or we already have enough?  Do not wait to run.
        if not delay or over_max_threshold or delay_expired:
            self.run(queue_entry)
        else:
            queue_entry.set_status(models.HostQueueEntry.Status.WAITING)

    def request_abort(self):
        """Request that this Job be aborted on the next scheduler cycle."""
        self.model().abort()

    def schedule_delayed_callback_task(self, queue_entry):
        queue_entry.set_status(models.HostQueueEntry.Status.PENDING)

        if self._delay_ready_task:
            return None

        delay = scheduler_config.config.secs_to_wait_for_atomic_group_hosts

        def run_job_after_delay():
            logging.info('Job %s done waiting for extra hosts.', self)
            # Check to see if the job is still relevant.  It could have aborted
            # while we were waiting or hosts could have disappeared, etc.
            if self._pending_count() < self._min_hosts_needed_to_run():
                logging.info('Job %s had too few Pending hosts after waiting '
                             'for extras.  Not running.', self)
                self.request_abort()
                return
            return self.run(queue_entry)

        logging.info('Job %s waiting up to %s seconds for more hosts.',
                     self.id, delay)
        self._delay_ready_task = DelayedCallTask(delay_seconds=delay,
                                                 callback=run_job_after_delay)
        return self._delay_ready_task

    def run(self, queue_entry):
        """
        :param queue_entry: The HostQueueEntry instance calling this method.
        """
        if queue_entry.atomic_group and self._atomic_and_has_started():
            logging.error('Job.run() called on running atomic Job %d '
                          'with HQE %s.', self.id, queue_entry)
            return
        queue_entries = self._choose_group_to_run(queue_entry)
        if queue_entries:
            self._finish_run(queue_entries)

    def _finish_run(self, queue_entries):
        for queue_entry in queue_entries:
            queue_entry.set_status(models.HostQueueEntry.Status.STARTING)
        self.abort_delay_ready_task()

    def abort_delay_ready_task(self):
        """Abort the delayed task associated with this job, if any."""
        if self._delay_ready_task:
            # Cancel any pending callback that would try to run again
            # as we are already running.
            self._delay_ready_task.abort()

    def __str__(self):
        return '%s-%s' % (self.id, self.owner)
