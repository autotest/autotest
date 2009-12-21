from django.db import models as dbmodels
import common
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.afe import model_logic, rpc_utils
from autotest_lib.new_tko.tko import models as tko_models
from autotest_lib.client.common_lib import enum


class Plan(dbmodels.Model):
    """A test plan

    Required:
        name: Plan name, unique
        complete: True if the plan is completed
        dirty: True if the plan has been changed since the execution engine has
               last seen it
        initialized: True if the plan has started

    Optional:
        label_override: A label to apply to each Autotest job.
        support: The global support object to apply to this plan
    """
    name = dbmodels.CharField(max_length=255, unique=True)
    label_override = dbmodels.CharField(max_length=255, null=True, blank=True)
    support = dbmodels.TextField(blank=True)
    complete = dbmodels.BooleanField(default=False)
    dirty = dbmodels.BooleanField(default=False)
    initialized = dbmodels.BooleanField(default=False)

    owners = dbmodels.ManyToManyField(afe_models.User,
                                      db_table='planner_plan_owners')
    hosts = dbmodels.ManyToManyField(afe_models.Host, through='Host')

    class Meta:
        db_table = 'planner_plans'


    def __unicode__(self):
        return unicode(self.name)


class ModelWithPlan(dbmodels.Model):
    """Superclass for models that have a plan_id

    Required:
        plan: The associated test plan
    """
    plan = dbmodels.ForeignKey(Plan)

    class Meta:
        abstract = True


    def __unicode__(self):
        return u'%s (%s)' % (self._get_details_unicode(), self.plan.name)


    def _get_details_unicode(self):
        """Gets the first part of the unicode string

        subclasses must override this method
        """
        raise NotImplementedError(
                'Subclasses must override _get_details_unicode()')


class Host(ModelWithPlan):
    """A plan host

    Required:
        host: The AFE host
        complete: True if and only if this host is finished in the test plan
        blocked: True if and only if the host is blocked (not executing tests)
    """
    host = dbmodels.ForeignKey(afe_models.Host)
    complete = dbmodels.BooleanField(default=False)
    blocked = dbmodels.BooleanField(default=False)

    class Meta:
        db_table = 'planner_hosts'


    def _get_details_unicode(self):
        return 'Host: %s' % host.hostname


class ControlFile(model_logic.ModelWithHash):
    """A control file. Immutable once added to the table

    Required:
        contents: The text of the control file

    Others:
        control_hash: The SHA1 hash of the control file, for duplicate detection
                      and fast search
    """
    contents = dbmodels.TextField()

    class Meta:
        db_table = 'planner_test_control_files'


    @classmethod
    def _compute_hash(cls, **kwargs):
        return rpc_utils.get_sha1_hash(kwargs['contents'])


    def __unicode__(self):
        return u'Control file id %s (SHA1: %s)' % (self.id, self.control_hash)


class Test(ModelWithPlan):
    """A planned test

    Required:
        test_control_file: The control file to run
        execution_order: An integer describing when this test should be run in
                         the test plan
    """
    control_file = dbmodels.ForeignKey(ControlFile)
    execution_order = dbmodels.IntegerField(blank=True)

    class Meta:
        db_table = 'planner_tests'
        ordering = ('execution_order',)


    def _get_details_unicode(self):
        return 'Planned test - Control file id %s' % test_control_file.id


class Job(ModelWithPlan):
    """Represents an Autotest job initiated for a test plan

    Required:
        test: The Test associated with this Job
        afe_job: The Autotest job
    """
    test = dbmodels.ForeignKey(Test)
    afe_job = dbmodels.ForeignKey(afe_models.Job)

    class Meta:
        db_table = 'planner_test_jobs'


    def _get_details_unicode(self):
        return 'AFE job %s' % afe_job.id


class Bug(dbmodels.Model):
    """Represents a bug ID

    Required:
        external_uid: External unique ID for the bug
    """
    external_uid = dbmodels.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'planner_bugs'


    def __unicode__(self):
        return u'Bug external ID %s' % self.external_uid


class TestRun(ModelWithPlan):
    """An individual test run from an Autotest job for the test plan.

    Each Job object may have multiple TestRun objects associated with it.

    Required:
        test_job: The Job object associated with this TestRun
        tko_test: The TKO Test associated with this TestRun
        status: One of 'Active', 'Passed', 'Failed'
        finalized: True if and only if the TestRun is ready to be shown in
                   triage
        invalidated: True if and only if a user has decided to invalidate this
                     TestRun's results
        seen: True if and only if a user has marked this TestRun as "seen"
        triaged: True if and only if the TestRun no longer requires any user
                 intervention

    Optional:
        bugs: Bugs filed that a relevant to this run
    """
    Status = enum.Enum('Active', 'Passed', 'Failed', string_values=True)

    test_job = dbmodels.ForeignKey(Job)
    tko_test = dbmodels.ForeignKey(tko_models.Test)
    status = dbmodels.CharField(max_length=16, choices=Status.choices())
    finalized = dbmodels.BooleanField(default=False)
    seen = dbmodels.BooleanField(default=False)
    triaged = dbmodels.BooleanField(default=False)

    bugs = dbmodels.ManyToManyField(Bug, null=True,
                                    db_table='planner_test_run_bugs')

    class Meta:
        db_table = 'planner_test_runs'


    def _get_details_unicode(self):
        return 'Test Run: %s' % self.id


class DataType(dbmodels.Model):
    """Encodes the data model types

    For use in the history table, to identify the type of object that was
    changed.

    Required:
        name: The name of the data type
        db_table: The name of the database table that stores this type
    """
    name = dbmodels.CharField(max_length=255)
    db_table = dbmodels.CharField(max_length=255)

    class Meta:
        db_table = 'planner_data_types'


    def __unicode__(self):
        return u'Data type %s (stored in table %s)' % (self.name, self.db_table)


class History(ModelWithPlan):
    """Represents a history action

    Required:
        action_id: An arbitrary ID that uniquely identifies the user action
                   related to the history entry. One user action may result in
                   multiple history entries
        user: The user who initiated the change
        data_type: The type of object that was changed
        object_id: Value of the primary key field for the changed object
        old_object_repr: A string representation of the object before the change
        new_object_repr: A string representation of the object after the change

    Others:
        time: A timestamp. Automatically generated.
    """
    action_id = dbmodels.IntegerField()
    user = dbmodels.ForeignKey(afe_models.User)
    data_type = dbmodels.ForeignKey(DataType)
    object_id = dbmodels.IntegerField()
    old_object_repr = dbmodels.TextField(blank=True)
    new_object_repr = dbmodels.TextField(blank=True)

    time = dbmodels.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'planner_history'


    def _get_details_unicode(self):
        return 'History entry: %s => %s' % (self.old_object_repr,
                                            self.new_object_repr)


class SavedObject(dbmodels.Model):
    """A saved object that can be recalled at certain points in the UI

    Required:
        user: The creator of the object
        object_type: One of 'support', 'triage', 'autoprocess', 'custom_query'
        name: The name given to the object
        encoded_object: The actual object
    """
    Type = enum.Enum('support', 'triage', 'autoprocess', 'custom_query',
                     string_values=True)

    user = dbmodels.ForeignKey(afe_models.User)
    object_type = dbmodels.CharField(max_length=16,
                                     choices=Type.choices(), db_column='type')
    name = dbmodels.CharField(max_length=255)
    encoded_object = dbmodels.TextField()

    class Meta:
        db_table = 'planner_saved_objects'
        unique_together = ('user', 'object_type', 'name')


    def __unicode__(self):
        return u'Saved %s object: %s, by %s' % (self.object_type, self.name,
                                                self.user.login)


class CustomQuery(ModelWithPlan):
    """A custom SQL query for the triage page

    Required:
        query: the SQL WHERE clause to attach to the main query
    """
    query = dbmodels.TextField()

    class Meta:
        db_table = 'planner_custom_queries'


    def _get_details_unicode(self):
        return 'Custom Query: %s' % self.query


class KeyVal(model_logic.ModelWithHash):
    """Represents a keyval. Immutable once added to the table.

    Required:
        key: The key
        value: The value

    Others:
        keyval_hash: The result of SHA1(SHA1(key) ++ value), for duplicate
                     detection and fast search.
    """
    key = dbmodels.CharField(max_length=1024)
    value = dbmodels.CharField(max_length=1024)

    class Meta:
        db_table = 'planner_keyvals'


    @classmethod
    def _compute_hash(cls, **kwargs):
        round1 = rpc_utils.get_sha1_hash(kwargs['key'])
        return rpc_utils.get_sha1_hash(round1 + kwargs['value'])


    def __unicode__(self):
        return u'Keyval: %s = %s' % (self.key, self.value)


class AutoProcess(ModelWithPlan):
    """An autoprocessing directive to perform on test runs that enter triage

    Required:
        condition: A SQL WHERE clause. The autoprocessing will be applied if the
                   test run matches this condition
        enabled: If this is False, this autoprocessing entry will not be applied

    Optional:
        labels: Labels to apply to the TKO test
        keyvals: Keyval overrides to apply to the TKO test
        bugs: Bugs filed that a relevant to this run
        reason_override: Override for the AFE reason
    """
    condition = dbmodels.TextField()
    enabled = dbmodels.BooleanField(default=False)

    labels = dbmodels.ManyToManyField(tko_models.TestLabel, null=True,
                                      db_table='planner_autoprocess_labels')
    keyvals = dbmodels.ManyToManyField(KeyVal, null=True,
                                       db_table='planner_autoprocess_keyvals')
    bugs = dbmodels.ManyToManyField(Bug, null=True,
                                    db_table='planner_autoprocess_bugs')
    reason_override = dbmodels.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'planner_autoprocess'


    def _get_details_unicode(self):
        return 'Autoprocessing condition: %s' % self.condition
