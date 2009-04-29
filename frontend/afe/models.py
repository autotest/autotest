from datetime import datetime
from django.db import models as dbmodels, connection
from frontend.afe import model_logic
from frontend import settings, thread_local
from autotest_lib.client.common_lib import enum, host_protections, global_config
from autotest_lib.client.common_lib import debug

logger = debug.get_logger()

# job options and user preferences
RebootBefore = enum.Enum('Never', 'If dirty', 'Always')
DEFAULT_REBOOT_BEFORE = RebootBefore.IF_DIRTY
RebootAfter = enum.Enum('Never', 'If all tests passed', 'Always')
DEFAULT_REBOOT_AFTER = RebootBefore.ALWAYS


class AclAccessViolation(Exception):
    """\
    Raised when an operation is attempted with proper permissions as
    dictated by ACLs.
    """


class AtomicGroup(model_logic.ModelWithInvalid, dbmodels.Model):
    """\
    An atomic group defines a collection of hosts which must only be scheduled
    all at once.  Any host with a label having an atomic group will only be
    scheduled for a job at the same time as other hosts sharing that label.

    Required:
      name: A name for this atomic group.  ex: 'rack23' or 'funky_net'
      max_number_of_machines: The maximum number of machines that will be
              scheduled at once when scheduling jobs to this atomic group.
              The job.synch_count is considered the minimum.

    Optional:
      description: Arbitrary text description of this group's purpose.
    """
    name = dbmodels.CharField(maxlength=255, unique=True)
    description = dbmodels.TextField(blank=True)
    max_number_of_machines = dbmodels.IntegerField(default=1)
    invalid = dbmodels.BooleanField(default=False,
                                    editable=settings.FULL_ADMIN)

    name_field = 'name'
    objects = model_logic.ExtendedManager()
    valid_objects = model_logic.ValidObjectsManager()


    def enqueue_job(self, job, is_template=False):
        """Enqueue a job on an associated atomic group of hosts."""
        queue_entry = HostQueueEntry.create(atomic_group=self, job=job,
                                            is_template=is_template)
        queue_entry.save()


    def clean_object(self):
        self.label_set.clear()


    class Meta:
        db_table = 'atomic_groups'

    class Admin:
        list_display = ('name', 'description', 'max_number_of_machines')
        # see Host.Admin
        manager = model_logic.ValidObjectsManager()

    def __str__(self):
        return self.name


class Label(model_logic.ModelWithInvalid, dbmodels.Model):
    """\
    Required:
      name: label name

    Optional:
      kernel_config: URL/path to kernel config for jobs run on this label.
      platform: If True, this is a platform label (defaults to False).
      only_if_needed: If True, a Host with this label can only be used if that
              label is requested by the job/test (either as the meta_host or
              in the job_dependencies).
      atomic_group: The atomic group associated with this label.
    """
    name = dbmodels.CharField(maxlength=255, unique=True)
    kernel_config = dbmodels.CharField(maxlength=255, blank=True)
    platform = dbmodels.BooleanField(default=False)
    invalid = dbmodels.BooleanField(default=False,
                                    editable=settings.FULL_ADMIN)
    only_if_needed = dbmodels.BooleanField(default=False)

    name_field = 'name'
    objects = model_logic.ExtendedManager()
    valid_objects = model_logic.ValidObjectsManager()
    atomic_group = dbmodels.ForeignKey(AtomicGroup, null=True, blank=True)


    def clean_object(self):
        self.host_set.clear()


    def enqueue_job(self, job, atomic_group=None, is_template=False):
        """Enqueue a job on any host of this label."""
        queue_entry = HostQueueEntry.create(meta_host=self, job=job,
                                            is_template=is_template,
                                            atomic_group=atomic_group)
        queue_entry.save()


    class Meta:
        db_table = 'labels'

    class Admin:
        list_display = ('name', 'kernel_config')
        # see Host.Admin
        manager = model_logic.ValidObjectsManager()

    def __str__(self):
        return self.name


class User(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Required:
    login :user login name

    Optional:
    access_level: 0=User (default), 1=Admin, 100=Root
    """
    ACCESS_ROOT = 100
    ACCESS_ADMIN = 1
    ACCESS_USER = 0

    login = dbmodels.CharField(maxlength=255, unique=True)
    access_level = dbmodels.IntegerField(default=ACCESS_USER, blank=True)

    # user preferences
    reboot_before = dbmodels.SmallIntegerField(choices=RebootBefore.choices(),
                                               blank=True,
                                               default=DEFAULT_REBOOT_BEFORE)
    reboot_after = dbmodels.SmallIntegerField(choices=RebootAfter.choices(),
                                              blank=True,
                                              default=DEFAULT_REBOOT_AFTER)
    show_experimental = dbmodels.BooleanField(default=False)

    name_field = 'login'
    objects = model_logic.ExtendedManager()


    def save(self):
        # is this a new object being saved for the first time?
        first_time = (self.id is None)
        user = thread_local.get_user()
        if user and not user.is_superuser() and user.login != self.login:
            raise AclAccessViolation("You cannot modify user " + self.login)
        super(User, self).save()
        if first_time:
            everyone = AclGroup.objects.get(name='Everyone')
            everyone.users.add(self)


    def is_superuser(self):
        return self.access_level >= self.ACCESS_ROOT


    class Meta:
        db_table = 'users'

    class Admin:
        list_display = ('login', 'access_level')
        search_fields = ('login',)

    def __str__(self):
        return self.login


class Host(model_logic.ModelWithInvalid, dbmodels.Model):
    """\
    Required:
    hostname

    optional:
    locked: if true, host is locked and will not be queued

    Internal:
    synch_id: currently unused
    status: string describing status of host
    invalid: true if the host has been deleted
    protection: indicates what can be done to this host during repair
    locked_by: user that locked the host, or null if the host is unlocked
    lock_time: DateTime at which the host was locked
    dirty: true if the host has been used without being rebooted
    """
    Status = enum.Enum('Verifying', 'Running', 'Ready', 'Repairing',
                       'Repair Failed', 'Dead', 'Cleaning', 'Pending',
                        string_values=True)

    hostname = dbmodels.CharField(maxlength=255, unique=True)
    labels = dbmodels.ManyToManyField(Label, blank=True,
                                      filter_interface=dbmodels.HORIZONTAL)
    locked = dbmodels.BooleanField(default=False)
    synch_id = dbmodels.IntegerField(blank=True, null=True,
                                     editable=settings.FULL_ADMIN)
    status = dbmodels.CharField(maxlength=255, default=Status.READY,
                                choices=Status.choices(),
                                editable=settings.FULL_ADMIN)
    invalid = dbmodels.BooleanField(default=False,
                                    editable=settings.FULL_ADMIN)
    protection = dbmodels.SmallIntegerField(null=False, blank=True,
                                            choices=host_protections.choices,
                                            default=host_protections.default)
    locked_by = dbmodels.ForeignKey(User, null=True, blank=True, editable=False)
    lock_time = dbmodels.DateTimeField(null=True, blank=True, editable=False)
    dirty = dbmodels.BooleanField(default=True, editable=settings.FULL_ADMIN)

    name_field = 'hostname'
    objects = model_logic.ExtendedManager()
    valid_objects = model_logic.ValidObjectsManager()


    def __init__(self, *args, **kwargs):
        super(Host, self).__init__(*args, **kwargs)
        self._record_attributes(['status'])


    @staticmethod
    def create_one_time_host(hostname):
        query = Host.objects.filter(hostname=hostname)
        if query.count() == 0:
            host = Host(hostname=hostname, invalid=True)
            host.do_validate()
        else:
            host = query[0]
            if not host.invalid:
                raise model_logic.ValidationError({
                    'hostname' : '%s already exists in the autotest DB.  '
                        'Select it rather than entering it as a one time '
                        'host.' % hostname
                    })
            host.clean_object()
            AclGroup.objects.get(name='Everyone').hosts.add(host)
            host.status = Host.Status.READY
        host.protection = host_protections.Protection.DO_NOT_REPAIR
        host.locked = False
        host.save()
        return host

    def clean_object(self):
        self.aclgroup_set.clear()
        self.labels.clear()


    def save(self):
        # extra spaces in the hostname can be a sneaky source of errors
        self.hostname = self.hostname.strip()
        # is this a new object being saved for the first time?
        first_time = (self.id is None)
        if not first_time:
            AclGroup.check_for_acl_violation_hosts([self])
        if self.locked and not self.locked_by:
            self.locked_by = thread_local.get_user()
            self.lock_time = datetime.now()
            self.dirty = True
        elif not self.locked and self.locked_by:
            self.locked_by = None
            self.lock_time = None
        super(Host, self).save()
        if first_time:
            everyone = AclGroup.objects.get(name='Everyone')
            everyone.hosts.add(self)
        self._check_for_updated_attributes()


    def delete(self):
        AclGroup.check_for_acl_violation_hosts([self])
        for queue_entry in self.hostqueueentry_set.all():
            queue_entry.deleted = True
            queue_entry.abort(thread_local.get_user())
        super(Host, self).delete()


    def on_attribute_changed(self, attribute, old_value):
        assert attribute == 'status'
        logger.info(self.hostname + ' -> ' + self.status)


    def enqueue_job(self, job, atomic_group=None, is_template=False):
        """Enqueue a job on this host."""
        queue_entry = HostQueueEntry.create(host=self, job=job,
                                            is_template=is_template,
                                            atomic_group=atomic_group)
        # allow recovery of dead hosts from the frontend
        if not self.active_queue_entry() and self.is_dead():
            self.status = Host.Status.READY
            self.save()
        queue_entry.save()

        block = IneligibleHostQueue(job=job, host=self)
        block.save()


    def platform(self):
        # TODO(showard): slighly hacky?
        platforms = self.labels.filter(platform=True)
        if len(platforms) == 0:
            return None
        return platforms[0]
    platform.short_description = 'Platform'


    def is_dead(self):
        return self.status == Host.Status.REPAIR_FAILED


    def active_queue_entry(self):
        active = list(self.hostqueueentry_set.filter(active=True))
        if not active:
            return None
        assert len(active) == 1, ('More than one active entry for '
                                  'host ' + self.hostname)
        return active[0]


    class Meta:
        db_table = 'hosts'

    class Admin:
        # TODO(showard) - showing platform requires a SQL query for
        # each row (since labels are many-to-many) - should we remove
        # it?
        list_display = ('hostname', 'platform', 'locked', 'status')
        list_filter = ('labels', 'locked', 'protection')
        search_fields = ('hostname', 'status')
        # undocumented Django feature - if you set manager here, the
        # admin code will use it, otherwise it'll use a default Manager
        manager = model_logic.ValidObjectsManager()

    def __str__(self):
        return self.hostname


class Test(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Required:
    author: author name
    description: description of the test
    name: test name
    time: short, medium, long
    test_class: This describes the class for your the test belongs in.
    test_category: This describes the category for your tests
    test_type: Client or Server
    path: path to pass to run_test()
    sync_count:  is a number >=1 (1 being the default). If it's 1, then it's an
                 async job. If it's >1 it's sync job for that number of machines
                 i.e. if sync_count = 2 it is a sync job that requires two
                 machines.
    Optional:
    dependencies: What the test requires to run. Comma deliminated list
    dependency_labels: many-to-many relationship with labels corresponding to
                       test dependencies.
    experimental: If this is set to True production servers will ignore the test
    run_verify: Whether or not the scheduler should run the verify stage
    """
    TestTime = enum.Enum('SHORT', 'MEDIUM', 'LONG', start_value=1)
    # TODO(showard) - this should be merged with Job.ControlType (but right
    # now they use opposite values)
    Types = enum.Enum('Client', 'Server', start_value=1)

    name = dbmodels.CharField(maxlength=255, unique=True)
    author = dbmodels.CharField(maxlength=255)
    test_class = dbmodels.CharField(maxlength=255)
    test_category = dbmodels.CharField(maxlength=255)
    dependencies = dbmodels.CharField(maxlength=255, blank=True)
    description = dbmodels.TextField(blank=True)
    experimental = dbmodels.BooleanField(default=True)
    run_verify = dbmodels.BooleanField(default=True)
    test_time = dbmodels.SmallIntegerField(choices=TestTime.choices(),
                                           default=TestTime.MEDIUM)
    test_type = dbmodels.SmallIntegerField(choices=Types.choices())
    sync_count = dbmodels.IntegerField(default=1)
    path = dbmodels.CharField(maxlength=255, unique=True)
    dependency_labels = dbmodels.ManyToManyField(
        Label, blank=True, filter_interface=dbmodels.HORIZONTAL)

    name_field = 'name'
    objects = model_logic.ExtendedManager()


    class Meta:
        db_table = 'autotests'

    class Admin:
        fields = (
            (None, {'fields' :
                    ('name', 'author', 'test_category', 'test_class',
                     'test_time', 'sync_count', 'test_type', 'sync_count',
                     'path', 'dependencies', 'experimental', 'run_verify',
                     'description')}),
            )
        list_display = ('name', 'test_type', 'description', 'sync_count')
        search_fields = ('name',)

    def __str__(self):
        return self.name


class Profiler(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Required:
    name: profiler name
    test_type: Client or Server

    Optional:
    description: arbirary text description
    """
    name = dbmodels.CharField(maxlength=255, unique=True)
    description = dbmodels.TextField(blank=True)

    name_field = 'name'
    objects = model_logic.ExtendedManager()


    class Meta:
        db_table = 'profilers'

    class Admin:
        list_display = ('name', 'description')
        search_fields = ('name',)

    def __str__(self):
        return self.name


class AclGroup(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Required:
    name: name of ACL group

    Optional:
    description: arbitrary description of group
    """
    name = dbmodels.CharField(maxlength=255, unique=True)
    description = dbmodels.CharField(maxlength=255, blank=True)
    users = dbmodels.ManyToManyField(User, blank=True,
                                     filter_interface=dbmodels.HORIZONTAL)
    hosts = dbmodels.ManyToManyField(Host,
                                     filter_interface=dbmodels.HORIZONTAL)

    name_field = 'name'
    objects = model_logic.ExtendedManager()

    @staticmethod
    def check_for_acl_violation_hosts(hosts):
        user = thread_local.get_user()
        if user.is_superuser():
            return
        accessible_host_ids = set(
            host.id for host in Host.objects.filter(aclgroup__users=user))
        for host in hosts:
            # Check if the user has access to this host,
            # but only if it is not a metahost
            if (isinstance(host, Host)
                and int(host.id) not in accessible_host_ids):
                raise AclAccessViolation("You do not have access to %s"
                                         % str(host))


    @staticmethod
    def check_abort_permissions(queue_entries):
        """
        look for queue entries that aren't abortable, meaning
         * the job isn't owned by this user, and
           * the machine isn't ACL-accessible, or
           * the machine is in the "Everyone" ACL
        """
        user = thread_local.get_user()
        if user.is_superuser():
            return
        not_owned = queue_entries.exclude(job__owner=user.login)
        # I do this using ID sets instead of just Django filters because
        # filtering on M2M fields is broken in Django 0.96.  It's better in 1.0.
        accessible_ids = set(
            entry.id for entry
            in not_owned.filter(host__aclgroup__users__login=user.login))
        public_ids = set(entry.id for entry
                         in not_owned.filter(host__aclgroup__name='Everyone'))
        cannot_abort = [entry for entry in not_owned.select_related()
                        if entry.id not in accessible_ids
                        or entry.id in public_ids]
        if len(cannot_abort) == 0:
            return
        entry_names = ', '.join('%s-%s/%s' % (entry.job.id, entry.job.owner,
                                              entry.host_or_metahost_name())
                                for entry in cannot_abort)
        raise AclAccessViolation('You cannot abort the following job entries: '
                                 + entry_names)


    def check_for_acl_violation_acl_group(self):
        user = thread_local.get_user()
        if user.is_superuser():
            return None
        if not user in self.users.all():
            raise AclAccessViolation("You do not have access to %s"
                                     % self.name)

    @staticmethod
    def on_host_membership_change():
        everyone = AclGroup.objects.get(name='Everyone')

        # find hosts that aren't in any ACL group and add them to Everyone
        # TODO(showard): this is a bit of a hack, since the fact that this query
        # works is kind of a coincidence of Django internals.  This trick
        # doesn't work in general (on all foreign key relationships).  I'll
        # replace it with a better technique when the need arises.
        orphaned_hosts = Host.valid_objects.filter(aclgroup__id__isnull=True)
        everyone.hosts.add(*orphaned_hosts.distinct())

        # find hosts in both Everyone and another ACL group, and remove them
        # from Everyone
        hosts_in_everyone = Host.valid_objects.filter_custom_join(
            '_everyone', aclgroup__name='Everyone')
        acled_hosts = hosts_in_everyone.exclude(aclgroup__name='Everyone')
        everyone.hosts.remove(*acled_hosts.distinct())


    def delete(self):
        if (self.name == 'Everyone'):
            raise AclAccessViolation("You cannot delete 'Everyone'!")
        self.check_for_acl_violation_acl_group()
        super(AclGroup, self).delete()
        self.on_host_membership_change()


    def add_current_user_if_empty(self):
        if not self.users.count():
            self.users.add(thread_local.get_user())


    # if you have a model attribute called "Manipulator", Django will
    # automatically insert it into the beginning of the superclass list
    # for the model's manipulators
    class Manipulator(object):
        """
        Custom manipulator to get notification when ACLs are changed through
        the admin interface.
        """
        def save(self, new_data):
            user = thread_local.get_user()
            if hasattr(self, 'original_object'):
                if (not user.is_superuser()
                    and self.original_object.name == 'Everyone'):
                    raise AclAccessViolation("You cannot modify 'Everyone'!")
                self.original_object.check_for_acl_violation_acl_group()
            obj = super(AclGroup.Manipulator, self).save(new_data)
            if not hasattr(self, 'original_object'):
                obj.users.add(thread_local.get_user())
            obj.add_current_user_if_empty()
            obj.on_host_membership_change()
            return obj

    class Meta:
        db_table = 'acl_groups'

    class Admin:
        list_display = ('name', 'description')
        search_fields = ('name',)

    def __str__(self):
        return self.name


class JobManager(model_logic.ExtendedManager):
    'Custom manager to provide efficient status counts querying.'
    def get_status_counts(self, job_ids):
        """\
        Returns a dictionary mapping the given job IDs to their status
        count dictionaries.
        """
        if not job_ids:
            return {}
        id_list = '(%s)' % ','.join(str(job_id) for job_id in job_ids)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT job_id, status, aborted, complete, COUNT(*)
            FROM host_queue_entries
            WHERE job_id IN %s
            GROUP BY job_id, status, aborted, complete
            """ % id_list)
        all_job_counts = {}
        for job_id in job_ids:
            all_job_counts[job_id] = {}
        for job_id, status, aborted, complete, count in cursor.fetchall():
            full_status = HostQueueEntry.compute_full_status(status, aborted,
                                                             complete)
            all_job_counts[job_id][full_status] = count
        return all_job_counts


    def populate_dependencies(self, jobs):
        if not jobs:
            return
        job_ids = ','.join(str(job['id']) for job in jobs)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT jobs.id, labels.name
            FROM jobs
            INNER JOIN jobs_dependency_labels
              ON jobs.id = jobs_dependency_labels.job_id
            INNER JOIN labels ON jobs_dependency_labels.label_id = labels.id
            WHERE jobs.id IN (%s)
            """ % job_ids)
        job_dependencies = {}
        for job_id, dependency in cursor.fetchall():
            job_dependencies.setdefault(job_id, []).append(dependency)
        for job in jobs:
            dependencies = ','.join(job_dependencies.get(job['id'], []))
            job['dependencies'] = dependencies


class Job(dbmodels.Model, model_logic.ModelExtensions):
    """\
    owner: username of job owner
    name: job name (does not have to be unique)
    priority: Low, Medium, High, Urgent (or 0-3)
    control_file: contents of control file
    control_type: Client or Server
    created_on: date of job creation
    submitted_on: date of job submission
    synch_count: how many hosts should be used per autoserv execution
    run_verify: Whether or not to run the verify phase
    timeout: hours until job times out
    email_list: list of people to email on completion delimited by any of:
                white space, ',', ':', ';'
    dependency_labels: many-to-many relationship with labels corresponding to
                       job dependencies
    reboot_before: Never, If dirty, or Always
    reboot_after: Never, If all tests passed, or Always
    """
    DEFAULT_TIMEOUT = global_config.global_config.get_config_value(
        'AUTOTEST_WEB', 'job_timeout_default', default=240)

    Priority = enum.Enum('Low', 'Medium', 'High', 'Urgent')
    ControlType = enum.Enum('Server', 'Client', start_value=1)

    owner = dbmodels.CharField(maxlength=255)
    name = dbmodels.CharField(maxlength=255)
    priority = dbmodels.SmallIntegerField(choices=Priority.choices(),
                                          blank=True, # to allow 0
                                          default=Priority.MEDIUM)
    control_file = dbmodels.TextField()
    control_type = dbmodels.SmallIntegerField(choices=ControlType.choices(),
                                              blank=True, # to allow 0
                                              default=ControlType.CLIENT)
    created_on = dbmodels.DateTimeField()
    synch_count = dbmodels.IntegerField(null=True, default=1)
    timeout = dbmodels.IntegerField(default=DEFAULT_TIMEOUT)
    run_verify = dbmodels.BooleanField(default=True)
    email_list = dbmodels.CharField(maxlength=250, blank=True)
    dependency_labels = dbmodels.ManyToManyField(
        Label, blank=True, filter_interface=dbmodels.HORIZONTAL)
    reboot_before = dbmodels.SmallIntegerField(choices=RebootBefore.choices(),
                                               blank=True,
                                               default=DEFAULT_REBOOT_BEFORE)
    reboot_after = dbmodels.SmallIntegerField(choices=RebootAfter.choices(),
                                              blank=True,
                                              default=DEFAULT_REBOOT_AFTER)


    # custom manager
    objects = JobManager()


    def is_server_job(self):
        return self.control_type == self.ControlType.SERVER


    @classmethod
    def create(cls, owner, name, priority, control_file, control_type,
               hosts, synch_count, timeout, run_verify, email_list,
               dependencies, reboot_before, reboot_after):
        """\
        Creates a job by taking some information (the listed args)
        and filling in the rest of the necessary information.
        """
        AclGroup.check_for_acl_violation_hosts(hosts)
        job = cls.add_object(
            owner=owner, name=name, priority=priority,
            control_file=control_file, control_type=control_type,
            synch_count=synch_count, timeout=timeout,
            run_verify=run_verify, email_list=email_list,
            reboot_before=reboot_before, reboot_after=reboot_after,
            created_on=datetime.now())

        job.dependency_labels = dependencies
        return job


    def queue(self, hosts, atomic_group=None, is_template=False):
        """Enqueue a job on the given hosts."""
        if atomic_group and not hosts:
            # No hosts or labels are required to queue an atomic group
            # Job.  However, if they are given, we respect them below.
            atomic_group.enqueue_job(self, is_template=is_template)
        for host in hosts:
            host.enqueue_job(self, atomic_group=atomic_group,
                             is_template=is_template)


    def create_recurring_job(self, start_date, loop_period, loop_count, owner):
        rec = RecurringRun(job=self, start_date=start_date,
                           loop_period=loop_period,
                           loop_count=loop_count,
                           owner=User.objects.get(login=owner))
        rec.save()
        return rec.id


    def user(self):
        try:
            return User.objects.get(login=self.owner)
        except self.DoesNotExist:
            return None


    def abort(self, aborted_by):
        for queue_entry in self.hostqueueentry_set.all():
            queue_entry.abort(aborted_by)


    class Meta:
        db_table = 'jobs'

    if settings.FULL_ADMIN:
        class Admin:
            list_display = ('id', 'owner', 'name', 'control_type')

    def __str__(self):
        return '%s (%s-%s)' % (self.name, self.id, self.owner)


class IneligibleHostQueue(dbmodels.Model, model_logic.ModelExtensions):
    job = dbmodels.ForeignKey(Job)
    host = dbmodels.ForeignKey(Host)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'ineligible_host_queues'

    if settings.FULL_ADMIN:
        class Admin:
            list_display = ('id', 'job', 'host')


class HostQueueEntry(dbmodels.Model, model_logic.ModelExtensions):
    Status = enum.Enum('Queued', 'Starting', 'Verifying', 'Pending', 'Running',
                       'Gathering', 'Parsing', 'Aborted', 'Completed',
                       'Failed', 'Stopped', 'Template', string_values=True)
    ACTIVE_STATUSES = (Status.STARTING, Status.VERIFYING, Status.PENDING,
                       Status.RUNNING, Status.GATHERING)
    COMPLETE_STATUSES = (Status.ABORTED, Status.COMPLETED, Status.FAILED,
                         Status.STOPPED, Status.TEMPLATE)

    job = dbmodels.ForeignKey(Job)
    host = dbmodels.ForeignKey(Host, blank=True, null=True)
    status = dbmodels.CharField(maxlength=255)
    meta_host = dbmodels.ForeignKey(Label, blank=True, null=True,
                                    db_column='meta_host')
    active = dbmodels.BooleanField(default=False)
    complete = dbmodels.BooleanField(default=False)
    deleted = dbmodels.BooleanField(default=False)
    execution_subdir = dbmodels.CharField(maxlength=255, blank=True, default='')
    # If atomic_group is set, this is a virtual HostQueueEntry that will
    # be expanded into many actual hosts within the group at schedule time.
    atomic_group = dbmodels.ForeignKey(AtomicGroup, blank=True, null=True)
    aborted = dbmodels.BooleanField(default=False)

    objects = model_logic.ExtendedManager()


    def __init__(self, *args, **kwargs):
        super(HostQueueEntry, self).__init__(*args, **kwargs)
        self._record_attributes(['status'])


    @classmethod
    def create(cls, job, host=None, meta_host=None, atomic_group=None,
                 is_template=False):
        if is_template:
            status = cls.Status.TEMPLATE
        else:
            status = cls.Status.QUEUED

        return cls(job=job, host=host, meta_host=meta_host,
                   atomic_group=atomic_group, status=status)


    def save(self):
        self._set_active_and_complete()
        super(HostQueueEntry, self).save()
        self._check_for_updated_attributes()


    def host_or_metahost_name(self):
        if self.host:
            return self.host.hostname
        else:
            assert self.meta_host
            return self.meta_host.name


    def _set_active_and_complete(self):
        if self.status in self.ACTIVE_STATUSES:
            self.active, self.complete = True, False
        elif self.status in self.COMPLETE_STATUSES:
            self.active, self.complete = False, True
        else:
            self.active, self.complete = False, False


    def on_attribute_changed(self, attribute, old_value):
        assert attribute == 'status'
        logger.info('%s/%d (%d) -> %s' % (self.host, self.job.id, self.id,
                                           self.status))


    def is_meta_host_entry(self):
        'True if this is a entry has a meta_host instead of a host.'
        return self.host is None and self.meta_host is not None


    def log_abort(self, user):
        if user is None:
            # automatic system abort (i.e. job timeout)
            return
        abort_log = AbortedHostQueueEntry(queue_entry=self, aborted_by=user)
        abort_log.save()


    def abort(self, user):
        # this isn't completely immune to race conditions since it's not atomic,
        # but it should be safe given the scheduler's behavior.
        if not self.complete and not self.aborted:
            self.log_abort(user)
            self.aborted = True
            self.save()


    @classmethod
    def compute_full_status(cls, status, aborted, complete):
        if aborted and not complete:
            return 'Aborted (%s)' % status
        return status


    def full_status(self):
        return self.compute_full_status(self.status, self.aborted,
                                        self.complete)


    def _postprocess_object_dict(self, object_dict):
        object_dict['full_status'] = self.full_status()


    class Meta:
        db_table = 'host_queue_entries'

    if settings.FULL_ADMIN:
        class Admin:
            list_display = ('id', 'job', 'host', 'status',
                            'meta_host')


class AbortedHostQueueEntry(dbmodels.Model, model_logic.ModelExtensions):
    queue_entry = dbmodels.OneToOneField(HostQueueEntry, primary_key=True)
    aborted_by = dbmodels.ForeignKey(User)
    aborted_on = dbmodels.DateTimeField()

    objects = model_logic.ExtendedManager()


    def save(self):
        self.aborted_on = datetime.now()
        super(AbortedHostQueueEntry, self).save()

    class Meta:
        db_table = 'aborted_host_queue_entries'


class RecurringRun(dbmodels.Model, model_logic.ModelExtensions):
    """\
    job: job to use as a template
    owner: owner of the instantiated template
    start_date: Run the job at scheduled date
    loop_period: Re-run (loop) the job periodically
                 (in every loop_period seconds)
    loop_count: Re-run (loop) count
    """

    job = dbmodels.ForeignKey(Job)
    owner = dbmodels.ForeignKey(User)
    start_date = dbmodels.DateTimeField()
    loop_period = dbmodels.IntegerField(blank=True)
    loop_count = dbmodels.IntegerField(blank=True)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'recurring_run'

    def __str__(self):
        return 'RecurringRun(job %s, start %s, period %s, count %s)' % (
            self.job.id, self.start_date, self.loop_period, self.loop_count)
