import logging, os
from datetime import datetime
from django.db import models as dbmodels, connection
from xml.sax import saxutils
try:
    import autotest.common as common
except ImportError:
    import common
from autotest_lib.frontend.afe import model_logic, model_attributes
from autotest_lib.frontend import settings, thread_local
from autotest_lib.client.common_lib import enum, host_protections, global_config
from autotest_lib.client.common_lib import host_queue_entry_states

# job options and user preferences
DEFAULT_REBOOT_BEFORE = model_attributes.RebootBefore.IF_DIRTY
DEFAULT_REBOOT_AFTER = model_attributes.RebootBefore.ALWAYS


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
    name = dbmodels.CharField(max_length=255, unique=True)
    description = dbmodels.TextField(blank=True)
    # This magic value is the default to simplify the scheduler logic.
    # It must be "large".  The common use of atomic groups is to want all
    # machines in the group to be used, limits on which subset used are
    # often chosen via dependency labels.
    INFINITE_MACHINES = 333333333
    max_number_of_machines = dbmodels.IntegerField(default=INFINITE_MACHINES)
    invalid = dbmodels.BooleanField(default=False,
                                  editable=settings.FULL_ADMIN)

    name_field = 'name'
    objects = model_logic.ModelWithInvalidManager()
    valid_objects = model_logic.ValidObjectsManager()


    def enqueue_job(self, job, is_template=False):
        """Enqueue a job on an associated atomic group of hosts."""
        queue_entry = HostQueueEntry.create(atomic_group=self, job=job,
                                            is_template=is_template)
        queue_entry.save()


    def clean_object(self):
        self.label_set.clear()


    class Meta:
        db_table = 'afe_atomic_groups'


    def __unicode__(self):
        return unicode(self.name)


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
    name = dbmodels.CharField(max_length=255, unique=True)
    kernel_config = dbmodels.CharField(max_length=255, blank=True)
    platform = dbmodels.BooleanField(default=False)
    invalid = dbmodels.BooleanField(default=False,
                                    editable=settings.FULL_ADMIN)
    only_if_needed = dbmodels.BooleanField(default=False)

    name_field = 'name'
    objects = model_logic.ModelWithInvalidManager()
    valid_objects = model_logic.ValidObjectsManager()
    atomic_group = dbmodels.ForeignKey(AtomicGroup, null=True, blank=True)


    def clean_object(self):
        self.host_set.clear()
        self.test_set.clear()


    def enqueue_job(self, job, atomic_group=None, is_template=False):
        """Enqueue a job on any host of this label."""
        queue_entry = HostQueueEntry.create(meta_host=self, job=job,
                                            is_template=is_template,
                                            atomic_group=atomic_group)
        queue_entry.save()


    class Meta:
        db_table = 'afe_labels'

    def __unicode__(self):
        return unicode(self.name)


class Drone(dbmodels.Model, model_logic.ModelExtensions):
    """
    A scheduler drone

    hostname: the drone's hostname
    """
    hostname = dbmodels.CharField(max_length=255, unique=True)

    name_field = 'hostname'
    objects = model_logic.ExtendedManager()


    def save(self, *args, **kwargs):
        if not User.current_user().is_superuser():
            raise Exception('Only superusers may edit drones')
        super(Drone, self).save(*args, **kwargs)


    def delete(self):
        if not User.current_user().is_superuser():
            raise Exception('Only superusers may delete drones')
        super(Drone, self).delete()


    class Meta:
        db_table = 'afe_drones'

    def __unicode__(self):
        return unicode(self.hostname)


class DroneSet(dbmodels.Model, model_logic.ModelExtensions):
    """
    A set of scheduler drones

    These will be used by the scheduler to decide what drones a job is allowed
    to run on.

    name: the drone set's name
    drones: the drones that are part of the set
    """
    DRONE_SETS_ENABLED = global_config.global_config.get_config_value(
            'SCHEDULER', 'drone_sets_enabled', type=bool, default=False)
    DEFAULT_DRONE_SET_NAME = global_config.global_config.get_config_value(
            'SCHEDULER', 'default_drone_set_name', default=None)

    name = dbmodels.CharField(max_length=255, unique=True)
    drones = dbmodels.ManyToManyField(Drone, db_table='afe_drone_sets_drones')

    name_field = 'name'
    objects = model_logic.ExtendedManager()


    def save(self, *args, **kwargs):
        if not User.current_user().is_superuser():
            raise Exception('Only superusers may edit drone sets')
        super(DroneSet, self).save(*args, **kwargs)


    def delete(self):
        if not User.current_user().is_superuser():
            raise Exception('Only superusers may delete drone sets')
        super(DroneSet, self).delete()


    @classmethod
    def drone_sets_enabled(cls):
        return cls.DRONE_SETS_ENABLED


    @classmethod
    def default_drone_set_name(cls):
        return cls.DEFAULT_DRONE_SET_NAME


    @classmethod
    def get_default(cls):
        return cls.smart_get(cls.DEFAULT_DRONE_SET_NAME)


    @classmethod
    def resolve_name(cls, drone_set_name):
        """
        Returns the name of one of these, if not None, in order of preference:
        1) the drone set given,
        2) the current user's default drone set, or
        3) the global default drone set

        or returns None if drone sets are disabled
        """
        if not cls.drone_sets_enabled():
            return None

        user = User.current_user()
        user_drone_set_name = user.drone_set and user.drone_set.name

        return drone_set_name or user_drone_set_name or cls.get_default().name


    def get_drone_hostnames(self):
        """
        Gets the hostnames of all drones in this drone set
        """
        return set(self.drones.all().values_list('hostname', flat=True))


    class Meta:
        db_table = 'afe_drone_sets'

    def __unicode__(self):
        return unicode(self.name)


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

    AUTOTEST_SYSTEM = 'autotest_system'

    login = dbmodels.CharField(max_length=255, unique=True)
    access_level = dbmodels.IntegerField(default=ACCESS_USER, blank=True)

    # user preferences
    reboot_before = dbmodels.SmallIntegerField(
        choices=model_attributes.RebootBefore.choices(), blank=True,
        default=DEFAULT_REBOOT_BEFORE)
    reboot_after = dbmodels.SmallIntegerField(
        choices=model_attributes.RebootAfter.choices(), blank=True,
        default=DEFAULT_REBOOT_AFTER)
    drone_set = dbmodels.ForeignKey(DroneSet, null=True, blank=True)
    show_experimental = dbmodels.BooleanField(default=False)

    name_field = 'login'
    objects = model_logic.ExtendedManager()


    def save(self, *args, **kwargs):
        # is this a new object being saved for the first time?
        first_time = (self.id is None)
        user = thread_local.get_user()
        if user and not user.is_superuser() and user.login != self.login:
            raise AclAccessViolation("You cannot modify user " + self.login)
        super(User, self).save(*args, **kwargs)
        if first_time:
            everyone = AclGroup.objects.get(name='Everyone')
            everyone.users.add(self)


    def is_superuser(self):
        return self.access_level >= self.ACCESS_ROOT


    @classmethod
    def current_user(cls):
        user = thread_local.get_user()
        if user is None:
            user, _ = cls.objects.get_or_create(login=cls.AUTOTEST_SYSTEM)
            user.access_level = cls.ACCESS_ROOT
            user.save()
        return user


    class Meta:
        db_table = 'afe_users'

    def __unicode__(self):
        return unicode(self.login)


class Host(model_logic.ModelWithInvalid, dbmodels.Model,
           model_logic.ModelWithAttributes):
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
                       'Repair Failed', 'Cleaning', 'Pending',
                       string_values=True)
    Protection = host_protections.Protection

    hostname = dbmodels.CharField(max_length=255, unique=True)
    labels = dbmodels.ManyToManyField(Label, blank=True,
                                      db_table='afe_hosts_labels')
    locked = dbmodels.BooleanField(default=False)
    synch_id = dbmodels.IntegerField(blank=True, null=True,
                                     editable=settings.FULL_ADMIN)
    status = dbmodels.CharField(max_length=255, default=Status.READY,
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
    objects = model_logic.ModelWithInvalidManager()
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
        host.protection = host_protections.Protection.DO_NOT_REPAIR
        host.locked = False
        host.save()
        host.clean_object()
        return host


    def resurrect_object(self, old_object):
        super(Host, self).resurrect_object(old_object)
        # invalid hosts can be in use by the scheduler (as one-time hosts), so
        # don't change the status
        self.status = old_object.status


    def clean_object(self):
        self.aclgroup_set.clear()
        self.labels.clear()


    def save(self, *args, **kwargs):
        # extra spaces in the hostname can be a sneaky source of errors
        self.hostname = self.hostname.strip()
        # is this a new object being saved for the first time?
        first_time = (self.id is None)
        if not first_time:
            AclGroup.check_for_acl_violation_hosts([self])
        if self.locked and not self.locked_by:
            self.locked_by = User.current_user()
            self.lock_time = datetime.now()
            self.dirty = True
        elif not self.locked and self.locked_by:
            self.locked_by = None
            self.lock_time = None
        super(Host, self).save(*args, **kwargs)
        if first_time:
            everyone = AclGroup.objects.get(name='Everyone')
            everyone.hosts.add(self)
        self._check_for_updated_attributes()


    def delete(self):
        AclGroup.check_for_acl_violation_hosts([self])
        for queue_entry in self.hostqueueentry_set.all():
            queue_entry.deleted = True
            queue_entry.abort()
        super(Host, self).delete()


    def on_attribute_changed(self, attribute, old_value):
        assert attribute == 'status'
        logging.info(self.hostname + ' -> ' + self.status)


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


    @classmethod
    def check_no_platform(cls, hosts):
        Host.objects.populate_relationships(hosts, Label, 'label_list')
        errors = []
        for host in hosts:
            platforms = [label.name for label in host.label_list
                         if label.platform]
            if platforms:
                # do a join, just in case this host has multiple platforms,
                # we'll be able to see it
                errors.append('Host %s already has a platform: %s' % (
                              host.hostname, ', '.join(platforms)))
        if errors:
            raise model_logic.ValidationError({'labels': '; '.join(errors)})


    def is_dead(self):
        return self.status == Host.Status.REPAIR_FAILED


    def active_queue_entry(self):
        active = list(self.hostqueueentry_set.filter(active=True))
        if not active:
            return None
        assert len(active) == 1, ('More than one active entry for '
                                  'host ' + self.hostname)
        return active[0]


    def _get_attribute_model_and_args(self, attribute):
        return HostAttribute, dict(host=self, attribute=attribute)


    class Meta:
        db_table = 'afe_hosts'

    def __unicode__(self):
        return unicode(self.hostname)


class HostAttribute(dbmodels.Model):
    """Arbitrary keyvals associated with hosts."""
    host = dbmodels.ForeignKey(Host)
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(max_length=300)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'afe_host_attributes'


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
    TestTypes = model_attributes.TestTypes
    # TODO(showard) - this should be merged with Job.ControlType (but right
    # now they use opposite values)

    name = dbmodels.CharField(max_length=255, unique=True)
    author = dbmodels.CharField(max_length=255)
    test_class = dbmodels.CharField(max_length=255)
    test_category = dbmodels.CharField(max_length=255)
    dependencies = dbmodels.CharField(max_length=255, blank=True)
    description = dbmodels.TextField(blank=True)
    experimental = dbmodels.BooleanField(default=True)
    run_verify = dbmodels.BooleanField(default=True)
    test_time = dbmodels.SmallIntegerField(choices=TestTime.choices(),
                                           default=TestTime.MEDIUM)
    test_type = dbmodels.SmallIntegerField(choices=TestTypes.choices())
    sync_count = dbmodels.IntegerField(default=1)
    path = dbmodels.CharField(max_length=255, unique=True)

    dependency_labels = (
        dbmodels.ManyToManyField(Label, blank=True,
                                 db_table='afe_autotests_dependency_labels'))
    name_field = 'name'
    objects = model_logic.ExtendedManager()


    def admin_description(self):
        escaped_description = saxutils.escape(self.description)
        return '<span style="white-space:pre">%s</span>' % escaped_description
    admin_description.allow_tags = True
    admin_description.short_description = 'Description'


    class Meta:
        db_table = 'afe_autotests'

    def __unicode__(self):
        return unicode(self.name)


class TestParameter(dbmodels.Model):
    """
    A declared parameter of a test
    """
    test = dbmodels.ForeignKey(Test)
    name = dbmodels.CharField(max_length=255)

    class Meta:
        db_table = 'afe_test_parameters'
        unique_together = ('test', 'name')

    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.test.name)


class Profiler(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Required:
    name: profiler name
    test_type: Client or Server

    Optional:
    description: arbirary text description
    """
    name = dbmodels.CharField(max_length=255, unique=True)
    description = dbmodels.TextField(blank=True)

    name_field = 'name'
    objects = model_logic.ExtendedManager()


    class Meta:
        db_table = 'afe_profilers'

    def __unicode__(self):
        return unicode(self.name)


class AclGroup(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Required:
    name: name of ACL group

    Optional:
    description: arbitrary description of group
    """
    name = dbmodels.CharField(max_length=255, unique=True)
    description = dbmodels.CharField(max_length=255, blank=True)
    users = dbmodels.ManyToManyField(User, blank=False,
                                     db_table='afe_acl_groups_users')
    hosts = dbmodels.ManyToManyField(Host, blank=True,
                                     db_table='afe_acl_groups_hosts')

    name_field = 'name'
    objects = model_logic.ExtendedManager()

    @staticmethod
    def check_for_acl_violation_hosts(hosts):
        user = User.current_user()
        if user.is_superuser():
            return
        accessible_host_ids = set(
            host.id for host in Host.objects.filter(aclgroup__users=user))
        for host in hosts:
            # Check if the user has access to this host,
            # but only if it is not a metahost or a one-time-host
            no_access = (isinstance(host, Host)
                         and not host.invalid
                         and int(host.id) not in accessible_host_ids)
            if no_access:
                raise AclAccessViolation("%s does not have access to %s" %
                                         (str(user), str(host)))


    @staticmethod
    def check_abort_permissions(queue_entries):
        """
        look for queue entries that aren't abortable, meaning
         * the job isn't owned by this user, and
           * the machine isn't ACL-accessible, or
           * the machine is in the "Everyone" ACL
        """
        user = User.current_user()
        if user.is_superuser():
            return
        not_owned = queue_entries.exclude(job__owner=user.login)
        # I do this using ID sets instead of just Django filters because
        # filtering on M2M dbmodels is broken in Django 0.96. It's better in
        # 1.0.
        # TODO: Use Django filters, now that we're using 1.0.
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
        user = User.current_user()
        if user.is_superuser():
            return
        if self.name == 'Everyone':
            raise AclAccessViolation("You cannot modify 'Everyone'!")
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
        hosts_in_everyone = Host.valid_objects.filter(aclgroup__name='Everyone')
        acled_hosts = set()
        for host in hosts_in_everyone:
            # Has an ACL group other than Everyone
            if host.aclgroup_set.count() > 1:
                acled_hosts.add(host)
        everyone.hosts.remove(*acled_hosts)


    def delete(self):
        if (self.name == 'Everyone'):
            raise AclAccessViolation("You cannot delete 'Everyone'!")
        self.check_for_acl_violation_acl_group()
        super(AclGroup, self).delete()
        self.on_host_membership_change()


    def add_current_user_if_empty(self):
        if not self.users.count():
            self.users.add(User.current_user())


    def perform_after_save(self, change):
        if not change:
            self.users.add(User.current_user())
        self.add_current_user_if_empty()
        self.on_host_membership_change()


    def save(self, *args, **kwargs):
        change = bool(self.id)
        if change:
            # Check the original object for an ACL violation
            AclGroup.objects.get(id=self.id).check_for_acl_violation_acl_group()
        super(AclGroup, self).save(*args, **kwargs)
        self.perform_after_save(change)


    class Meta:
        db_table = 'afe_acl_groups'

    def __unicode__(self):
        return unicode(self.name)


class Kernel(dbmodels.Model):
    """
    A kernel configuration for a parameterized job
    """
    version = dbmodels.CharField(max_length=255)
    cmdline = dbmodels.CharField(max_length=255, blank=True)

    @classmethod
    def create_kernels(cls, kernel_list):
        """
        Creates all kernels in the kernel list

        @param kernel_list A list of dictionaries that describe the kernels, in
                           the same format as the 'kernel' argument to
                           rpc_interface.generate_control_file
        @returns a list of the created kernels
        """
        if not kernel_list:
            return None
        return [cls._create(kernel) for kernel in kernel_list]


    @classmethod
    def _create(cls, kernel_dict):
        version = kernel_dict.pop('version')
        cmdline = kernel_dict.pop('cmdline', '')

        if kernel_dict:
            raise Exception('Extraneous kernel arguments remain: %r'
                            % kernel_dict)

        kernel, _ = cls.objects.get_or_create(version=version,
                                              cmdline=cmdline)
        return kernel


    class Meta:
        db_table = 'afe_kernels'
        unique_together = ('version', 'cmdline')

    def __unicode__(self):
        return u'%s %s' % (self.version, self.cmdline)


class ParameterizedJob(dbmodels.Model):
    """
    Auxiliary configuration for a parameterized job
    """
    test = dbmodels.ForeignKey(Test)
    label = dbmodels.ForeignKey(Label, null=True)
    use_container = dbmodels.BooleanField(default=False)
    profile_only = dbmodels.BooleanField(default=False)
    upload_kernel_config = dbmodels.BooleanField(default=False)

    kernels = dbmodels.ManyToManyField(
            Kernel, db_table='afe_parameterized_job_kernels')
    profilers = dbmodels.ManyToManyField(
            Profiler, through='ParameterizedJobProfiler')


    @classmethod
    def smart_get(cls, id_or_name, *args, **kwargs):
        """For compatibility with Job.add_object"""
        return cls.objects.get(pk=id_or_name)


    def job(self):
        jobs = self.job_set.all()
        assert jobs.count() <= 1
        return jobs and jobs[0] or None


    class Meta:
        db_table = 'afe_parameterized_jobs'

    def __unicode__(self):
        return u'%s (parameterized) - %s' % (self.test.name, self.job())


class ParameterizedJobProfiler(dbmodels.Model):
    """
    A profiler to run on a parameterized job
    """
    parameterized_job = dbmodels.ForeignKey(ParameterizedJob)
    profiler = dbmodels.ForeignKey(Profiler)

    class Meta:
        db_table = 'afe_parameterized_jobs_profilers'
        unique_together = ('parameterized_job', 'profiler')


class ParameterizedJobProfilerParameter(dbmodels.Model):
    """
    A parameter for a profiler in a parameterized job
    """
    parameterized_job_profiler = dbmodels.ForeignKey(ParameterizedJobProfiler)
    parameter_name = dbmodels.CharField(max_length=255)
    parameter_value = dbmodels.TextField()
    parameter_type = dbmodels.CharField(
            max_length=8, choices=model_attributes.ParameterTypes.choices())

    class Meta:
        db_table = 'afe_parameterized_job_profiler_parameters'
        unique_together = ('parameterized_job_profiler', 'parameter_name')

    def __unicode__(self):
        return u'%s - %s' % (self.parameterized_job_profiler.profiler.name,
                             self.parameter_name)


class ParameterizedJobParameter(dbmodels.Model):
    """
    Parameters for a parameterized job
    """
    parameterized_job = dbmodels.ForeignKey(ParameterizedJob)
    test_parameter = dbmodels.ForeignKey(TestParameter)
    parameter_value = dbmodels.TextField()
    parameter_type = dbmodels.CharField(
            max_length=8, choices=model_attributes.ParameterTypes.choices())

    class Meta:
        db_table = 'afe_parameterized_job_parameters'
        unique_together = ('parameterized_job', 'test_parameter')

    def __unicode__(self):
        return u'%s - %s' % (self.parameterized_job.job().name,
                             self.test_parameter.name)


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
            FROM afe_host_queue_entries
            WHERE job_id IN %s
            GROUP BY job_id, status, aborted, complete
            """ % id_list)
        all_job_counts = dict((job_id, {}) for job_id in job_ids)
        for job_id, status, aborted, complete, count in cursor.fetchall():
            job_dict = all_job_counts[job_id]
            full_status = HostQueueEntry.compute_full_status(status, aborted,
                                                             complete)
            job_dict.setdefault(full_status, 0)
            job_dict[full_status] += count
        return all_job_counts


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
    timeout: hours from queuing time until job times out
    max_runtime_hrs: hours from job starting time until job times out
    email_list: list of people to email on completion delimited by any of:
                white space, ',', ':', ';'
    dependency_labels: many-to-many relationship with labels corresponding to
                       job dependencies
    reboot_before: Never, If dirty, or Always
    reboot_after: Never, If all tests passed, or Always
    parse_failed_repair: if True, a failed repair launched by this job will have
    its results parsed as part of the job.
    drone_set: The set of drones to run this job on
    """
    DEFAULT_TIMEOUT = global_config.global_config.get_config_value(
        'AUTOTEST_WEB', 'job_timeout_default', default=240)
    DEFAULT_MAX_RUNTIME_HRS = global_config.global_config.get_config_value(
        'AUTOTEST_WEB', 'job_max_runtime_hrs_default', default=72)
    DEFAULT_PARSE_FAILED_REPAIR = global_config.global_config.get_config_value(
        'AUTOTEST_WEB', 'parse_failed_repair_default', type=bool,
        default=False)

    Priority = enum.Enum('Low', 'Medium', 'High', 'Urgent')
    ControlType = enum.Enum('Server', 'Client', start_value=1)

    owner = dbmodels.CharField(max_length=255)
    name = dbmodels.CharField(max_length=255)
    priority = dbmodels.SmallIntegerField(choices=Priority.choices(),
                                          blank=True, # to allow 0
                                          default=Priority.MEDIUM)
    control_file = dbmodels.TextField(null=True, blank=True)
    control_type = dbmodels.SmallIntegerField(choices=ControlType.choices(),
                                              blank=True, # to allow 0
                                              default=ControlType.CLIENT)
    created_on = dbmodels.DateTimeField()
    synch_count = dbmodels.IntegerField(null=True, default=1)
    timeout = dbmodels.IntegerField(default=DEFAULT_TIMEOUT)
    run_verify = dbmodels.BooleanField(default=True)
    email_list = dbmodels.CharField(max_length=250, blank=True)
    dependency_labels = (
            dbmodels.ManyToManyField(Label, blank=True,
                                     db_table='afe_jobs_dependency_labels'))
    reboot_before = dbmodels.SmallIntegerField(
        choices=model_attributes.RebootBefore.choices(), blank=True,
        default=DEFAULT_REBOOT_BEFORE)
    reboot_after = dbmodels.SmallIntegerField(
        choices=model_attributes.RebootAfter.choices(), blank=True,
        default=DEFAULT_REBOOT_AFTER)
    parse_failed_repair = dbmodels.BooleanField(
        default=DEFAULT_PARSE_FAILED_REPAIR)
    max_runtime_hrs = dbmodels.IntegerField(default=DEFAULT_MAX_RUNTIME_HRS)
    drone_set = dbmodels.ForeignKey(DroneSet, null=True, blank=True)

    parameterized_job = dbmodels.ForeignKey(ParameterizedJob, null=True,
                                            blank=True)


    # custom manager
    objects = JobManager()


    def is_server_job(self):
        return self.control_type == self.ControlType.SERVER


    @classmethod
    def parameterized_jobs_enabled(cls):
        return global_config.global_config.get_config_value(
                'AUTOTEST_WEB', 'parameterized_jobs', type=bool)


    @classmethod
    def check_parameterized_job(cls, control_file, parameterized_job):
        """
        Checks that the job is valid given the global config settings

        First, either control_file must be set, or parameterized_job must be
        set, but not both. Second, parameterized_job must be set if and only if
        the parameterized_jobs option in the global config is set to True.
        """
        if not (bool(control_file) ^ bool(parameterized_job)):
            raise Exception('Job must have either control file or '
                            'parameterization, but not both')

        parameterized_jobs_enabled = cls.parameterized_jobs_enabled()
        if control_file and parameterized_jobs_enabled:
            raise Exception('Control file specified, but parameterized jobs '
                            'are enabled')
        if parameterized_job and not parameterized_jobs_enabled:
            raise Exception('Parameterized job specified, but parameterized '
                            'jobs are not enabled')


    @classmethod
    def create(cls, owner, options, hosts):
        """\
        Creates a job by taking some information (the listed args)
        and filling in the rest of the necessary information.
        """
        AclGroup.check_for_acl_violation_hosts(hosts)

        control_file = options.get('control_file')
        parameterized_job = options.get('parameterized_job')
        cls.check_parameterized_job(control_file=control_file,
                                    parameterized_job=parameterized_job)

        user = User.current_user()
        if options.get('reboot_before') is None:
            options['reboot_before'] = user.get_reboot_before_display()
        if options.get('reboot_after') is None:
            options['reboot_after'] = user.get_reboot_after_display()

        drone_set = DroneSet.resolve_name(options.get('drone_set'))

        job = cls.add_object(
            owner=owner,
            name=options['name'],
            priority=options['priority'],
            control_file=control_file,
            control_type=options['control_type'],
            synch_count=options.get('synch_count'),
            timeout=options.get('timeout'),
            max_runtime_hrs=options.get('max_runtime_hrs'),
            run_verify=options.get('run_verify'),
            email_list=options.get('email_list'),
            reboot_before=options.get('reboot_before'),
            reboot_after=options.get('reboot_after'),
            parse_failed_repair=options.get('parse_failed_repair'),
            created_on=datetime.now(),
            drone_set=drone_set,
            parameterized_job=parameterized_job)

        job.dependency_labels = options['dependencies']

        if options.get('keyvals'):
            for key, value in options['keyvals'].iteritems():
                JobKeyval.objects.create(job=job, key=key, value=value)

        return job


    def save(self, *args, **kwargs):
        self.check_parameterized_job(control_file=self.control_file,
                                     parameterized_job=self.parameterized_job)
        super(Job, self).save(*args, **kwargs)


    def queue(self, hosts, atomic_group=None, is_template=False):
        """Enqueue a job on the given hosts."""
        if not hosts:
            if atomic_group:
                # No hosts or labels are required to queue an atomic group
                # Job.  However, if they are given, we respect them below.
                atomic_group.enqueue_job(self, is_template=is_template)
            else:
                # hostless job
                entry = HostQueueEntry.create(job=self, is_template=is_template)
                entry.save()
            return

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


    def abort(self):
        for queue_entry in self.hostqueueentry_set.all():
            queue_entry.abort()


    def tag(self):
        return '%s-%s' % (self.id, self.owner)


    def keyval_dict(self):
        return dict((keyval.key, keyval.value)
                    for keyval in self.jobkeyval_set.all())


    class Meta:
        db_table = 'afe_jobs'

    def __unicode__(self):
        return u'%s (%s-%s)' % (self.name, self.id, self.owner)


class JobKeyval(dbmodels.Model, model_logic.ModelExtensions):
    """Keyvals associated with jobs"""
    job = dbmodels.ForeignKey(Job)
    key = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(max_length=300)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'afe_job_keyvals'


class IneligibleHostQueue(dbmodels.Model, model_logic.ModelExtensions):
    job = dbmodels.ForeignKey(Job)
    host = dbmodels.ForeignKey(Host)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'afe_ineligible_host_queues'


class HostQueueEntry(dbmodels.Model, model_logic.ModelExtensions):
    Status = host_queue_entry_states.Status
    ACTIVE_STATUSES = host_queue_entry_states.ACTIVE_STATUSES
    COMPLETE_STATUSES = host_queue_entry_states.COMPLETE_STATUSES

    job = dbmodels.ForeignKey(Job)
    host = dbmodels.ForeignKey(Host, blank=True, null=True)
    status = dbmodels.CharField(max_length=255)
    meta_host = dbmodels.ForeignKey(Label, blank=True, null=True,
                                    db_column='meta_host')
    active = dbmodels.BooleanField(default=False)
    complete = dbmodels.BooleanField(default=False)
    deleted = dbmodels.BooleanField(default=False)
    execution_subdir = dbmodels.CharField(max_length=255, blank=True,
                                          default='')
    # If atomic_group is set, this is a virtual HostQueueEntry that will
    # be expanded into many actual hosts within the group at schedule time.
    atomic_group = dbmodels.ForeignKey(AtomicGroup, blank=True, null=True)
    aborted = dbmodels.BooleanField(default=False)
    started_on = dbmodels.DateTimeField(null=True, blank=True)
    profile = dbmodels.CharField(max_length=255, blank=True, default='')

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


    def save(self, *args, **kwargs):
        self._set_active_and_complete()
        super(HostQueueEntry, self).save(*args, **kwargs)
        self._check_for_updated_attributes()


    def execution_path(self):
        """
        Path to this entry's results (relative to the base results directory).
        """
        return os.path.join(self.job.tag(), self.execution_subdir)


    def host_or_metahost_name(self):
        if self.host:
            return self.host.hostname
        elif self.meta_host:
            return self.meta_host.name
        else:
            assert self.atomic_group, "no host, meta_host or atomic group!"
            return self.atomic_group.name


    def _set_active_and_complete(self):
        if self.status in self.ACTIVE_STATUSES:
            self.active, self.complete = True, False
        elif self.status in self.COMPLETE_STATUSES:
            self.active, self.complete = False, True
        else:
            self.active, self.complete = False, False


    def on_attribute_changed(self, attribute, old_value):
        assert attribute == 'status'
        logging.info('%s/%d (%d) -> %s' % (self.host, self.job.id, self.id,
                                           self.status))


    def is_meta_host_entry(self):
        'True if this is a entry has a meta_host instead of a host.'
        return self.host is None and self.meta_host is not None


    def log_abort(self, user):
        abort_log = AbortedHostQueueEntry(queue_entry=self, aborted_by=user)
        abort_log.save()


    def abort(self):
        # this isn't completely immune to race conditions since it's not atomic,
        # but it should be safe given the scheduler's behavior.
        if not self.complete and not self.aborted:
            self.log_abort(User.current_user())
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
        db_table = 'afe_host_queue_entries'



    def __unicode__(self):
        hostname = None
        if self.host:
            hostname = self.host.hostname
        return u"%s/%d (%d)" % (hostname, self.job.id, self.id)


class AbortedHostQueueEntry(dbmodels.Model, model_logic.ModelExtensions):
    queue_entry = dbmodels.OneToOneField(HostQueueEntry, primary_key=True)
    aborted_by = dbmodels.ForeignKey(User)
    aborted_on = dbmodels.DateTimeField()

    objects = model_logic.ExtendedManager()


    def save(self, *args, **kwargs):
        self.aborted_on = datetime.now()
        super(AbortedHostQueueEntry, self).save(*args, **kwargs)

    class Meta:
        db_table = 'afe_aborted_host_queue_entries'


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
        db_table = 'afe_recurring_run'

    def __unicode__(self):
        return u'RecurringRun(job %s, start %s, period %s, count %s)' % (
            self.job.id, self.start_date, self.loop_period, self.loop_count)


class SpecialTask(dbmodels.Model, model_logic.ModelExtensions):
    """\
    Tasks to run on hosts at the next time they are in the Ready state. Use this
    for high-priority tasks, such as forced repair or forced reinstall.

    host: host to run this task on
    task: special task to run
    time_requested: date and time the request for this task was made
    is_active: task is currently running
    is_complete: task has finished running
    time_started: date and time the task started
    queue_entry: Host queue entry waiting on this task (or None, if task was not
                 started in preparation of a job)
    """
    Task = enum.Enum('Verify', 'Cleanup', 'Repair', string_values=True)

    host = dbmodels.ForeignKey(Host, blank=False, null=False)
    task = dbmodels.CharField(max_length=64, choices=Task.choices(),
                              blank=False, null=False)
    requested_by = dbmodels.ForeignKey(User)
    time_requested = dbmodels.DateTimeField(auto_now_add=True, blank=False,
                                            null=False)
    is_active = dbmodels.BooleanField(default=False, blank=False, null=False)
    is_complete = dbmodels.BooleanField(default=False, blank=False, null=False)
    time_started = dbmodels.DateTimeField(null=True, blank=True)
    queue_entry = dbmodels.ForeignKey(HostQueueEntry, blank=True, null=True)
    success = dbmodels.BooleanField(default=False, blank=False, null=False)

    objects = model_logic.ExtendedManager()


    def save(self, **kwargs):
        if self.queue_entry:
            self.requested_by = User.objects.get(
                    login=self.queue_entry.job.owner)
        super(SpecialTask, self).save(**kwargs)


    def execution_path(self):
        """@see HostQueueEntry.execution_path()"""
        return 'hosts/%s/%s-%s' % (self.host.hostname, self.id,
                                   self.task.lower())


    # property to emulate HostQueueEntry.status
    @property
    def status(self):
        """
        Return a host queue entry status appropriate for this task.  Although
        SpecialTasks are not HostQueueEntries, it is helpful to the user to
        present similar statuses.
        """
        if self.is_complete:
            if self.success:
                return HostQueueEntry.Status.COMPLETED
            return HostQueueEntry.Status.FAILED
        if self.is_active:
            return HostQueueEntry.Status.RUNNING
        return HostQueueEntry.Status.QUEUED


    # property to emulate HostQueueEntry.started_on
    @property
    def started_on(self):
        return self.time_started


    @classmethod
    def schedule_special_task(cls, host, task):
        """
        Schedules a special task on a host if the task is not already scheduled.
        """
        existing_tasks = SpecialTask.objects.filter(host__id=host.id, task=task,
                                                    is_active=False,
                                                    is_complete=False)
        if existing_tasks:
            return existing_tasks[0]

        special_task = SpecialTask(host=host, task=task,
                                   requested_by=User.current_user())
        special_task.save()
        return special_task


    def activate(self):
        """
        Sets a task as active and sets the time started to the current time.
        """
        logging.info('Starting: %s', self)
        self.is_active = True
        self.time_started = datetime.now()
        self.save()


    def finish(self, success):
        """
        Sets a task as completed
        """
        logging.info('Finished: %s', self)
        self.is_active = False
        self.is_complete = True
        self.success = success
        self.save()


    class Meta:
        db_table = 'afe_special_tasks'


    def __unicode__(self):
        result = u'Special Task %s (host %s, task %s, time %s)' % (
            self.id, self.host, self.task, self.time_requested)
        if self.is_complete:
            result += u' (completed)'
        elif self.is_active:
            result += u' (active)'

        return result
