from django.db import models as dbmodels, connection
from autotest.frontend.afe import model_logic, readonly_connection
from autotest.frontend.afe.models import TestEnvironment

_quote_name = connection.ops.quote_name


class TempManager(model_logic.ExtendedManager):
    _GROUP_COUNT_NAME = 'group_count'

    def _get_key_unless_is_function(self, field):
        if '(' in field:
            return field
        return self.get_key_on_this_table(field)

    def _get_field_names(self, fields, extra_select_fields={}):
        field_names = []
        for field in fields:
            if field in extra_select_fields:
                field_names.append(extra_select_fields[field][0])
            else:
                field_names.append(self._get_key_unless_is_function(field))
        return field_names

    def _get_group_query_sql(self, query, group_by):
        compiler = query.query.get_compiler(using=query.db)
        sql, params = compiler.as_sql()

        # insert GROUP BY clause into query
        group_fields = self._get_field_names(group_by, query.query.extra_select)
        group_by_clause = ' GROUP BY ' + ', '.join(group_fields)
        group_by_position = sql.rfind('ORDER BY')
        if group_by_position == -1:
            group_by_position = len(sql)
        sql = (sql[:group_by_position] +
               group_by_clause + ' ' +
               sql[group_by_position:])

        return sql, params

    def _get_column_names(self, cursor):
        """
        Gets the column names from the cursor description. This method exists
        so that it can be mocked in the unit test for sqlite3 compatibility.
        """
        return [column_info[0] for column_info in cursor.description]

    def execute_group_query(self, query, group_by):
        """
        Performs the given query grouped by the fields in group_by with the
        given query's extra select fields added.  Returns a list of dicts, where
        each dict corresponds to single row and contains a key for each grouped
        field as well as all of the extra select fields.
        """
        sql, params = self._get_group_query_sql(query, group_by)
        cursor = readonly_connection.connection().cursor()
        cursor.execute(sql, params)
        field_names = self._get_column_names(cursor)
        row_dicts = [dict(zip(field_names, row)) for row in cursor.fetchall()]
        return row_dicts

    def get_count_sql(self, query):
        """
        Get the SQL to properly select a per-group count of unique matches for
        a grouped query.  Returns a tuple (field alias, field SQL)
        """
        if query.query.distinct:
            pk_field = self.get_key_on_this_table()
            count_sql = 'COUNT(DISTINCT %s)' % pk_field
        else:
            count_sql = 'COUNT(1)'
        return self._GROUP_COUNT_NAME, count_sql

    def _get_num_groups_sql(self, query, group_by):
        group_fields = self._get_field_names(group_by, query.query.extra_select)
        query = query.order_by()  # this can mess up the query and isn't needed

        compiler = query.query.get_compiler(using=query.db)
        sql, params = compiler.as_sql()
        from_ = sql[sql.find(' FROM'):]
        return ('SELECT DISTINCT %s %s' % (','.join(group_fields),
                                           from_),
                params)

    def _cursor_rowcount(self, cursor):
        """To be stubbed by tests"""
        return cursor.rowcount

    def get_num_groups(self, query, group_by):
        """
        Returns the number of distinct groups for the given query grouped by the
        fields in group_by.
        """
        sql, params = self._get_num_groups_sql(query, group_by)
        cursor = readonly_connection.connection().cursor()
        cursor.execute(sql, params)
        return self._cursor_rowcount(cursor)


class Machine(dbmodels.Model):

    '''
    A machine used to run a test
    '''
    #: A numeric and automatic integer that uniquely identifies a given
    #: machine. This is the primary key for the resulting table created
    #: from this model.
    machine_idx = dbmodels.AutoField(primary_key=True)
    #: The name, such as a FQDN, of the machine that run the test. Must be
    #: unique.
    hostname = dbmodels.CharField(unique=True, max_length=255)
    #: the machine group
    machine_group = dbmodels.CharField(blank=True, max_length=240)
    #: the machine owner
    owner = dbmodels.CharField(blank=True, max_length=240)

    class Meta:
        db_table = 'tko_machines'


class Kernel(dbmodels.Model):

    '''
    The Linux Kernel used during a test
    '''
    #: A numeric and automatic integer that uniquely identifies a given
    #: machine. This is the primary key for the resulting table created
    #: from this model.
    kernel_idx = dbmodels.AutoField(primary_key=True)
    #: the kernel hash
    kernel_hash = dbmodels.CharField(max_length=105, editable=False)
    #: base
    base = dbmodels.CharField(max_length=90)
    #: printable
    printable = dbmodels.CharField(max_length=300)

    class Meta:
        db_table = 'tko_kernels'


class Patch(dbmodels.Model):

    '''
    A Patch applied to a Linux Kernel source during the build process
    '''
    #: A reference to a :class:`Kernel`
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    #: A descriptive name for the patch
    name = dbmodels.CharField(blank=True, max_length=240)
    #: The URL where the patch was fetched from
    url = dbmodels.CharField(blank=True, max_length=900)
    #: hash
    the_hash = dbmodels.CharField(blank=True, max_length=105, db_column='hash')

    class Meta:
        db_table = 'tko_patches'


class Status(dbmodels.Model):

    '''
    The possible results of a test

    These objects are populated automatically from a
    :ref:`fixture file <django:initial-data-via-fixtures>`
    '''
    #: A numeric and automatic integer that uniquely identifies a given
    #: machine. This is the primary key for the resulting table created
    #: from this model.
    status_idx = dbmodels.AutoField(primary_key=True)
    #: A short descriptive name for the status. This exact name is searched for
    #: while the TKO parser is reading and parsing status files
    word = dbmodels.CharField(max_length=30)

    class Meta:
        db_table = 'tko_status'


class Job(dbmodels.Model, model_logic.ModelExtensions):

    """
    A test job, having one or many tests an their results
    """
    job_idx = dbmodels.AutoField(primary_key=True)
    tag = dbmodels.CharField(unique=True, max_length=100)
    label = dbmodels.CharField(max_length=300)
    username = dbmodels.CharField(max_length=240)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    queued_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)
    finished_time = dbmodels.DateTimeField(null=True, blank=True)

    #: If this job was scheduled through the AFE application, this points
    #: to the related :class:`autotest.frontend.afe.models.Job` object
    afe_job_id = dbmodels.IntegerField(null=True, default=None)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'tko_jobs'


class JobKeyval(dbmodels.Model):
    job = dbmodels.ForeignKey(Job)
    key = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(blank=True, max_length=300)

    class Meta:
        db_table = 'tko_job_keyvals'


class Test(dbmodels.Model, model_logic.ModelExtensions,
           model_logic.ModelWithAttributes):
    test_idx = dbmodels.AutoField(primary_key=True)
    job = dbmodels.ForeignKey(Job, db_column='job_idx')
    test = dbmodels.CharField(max_length=300)
    subdir = dbmodels.CharField(blank=True, max_length=300)
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    status = dbmodels.ForeignKey(Status, db_column='status')
    reason = dbmodels.CharField(blank=True, max_length=3072)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    finished_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)

    #: a reference to a :class:`TestEnvironment` that better describes
    #: the environment (OS, packages, etc) where the test run
    test_environment = dbmodels.ForeignKey(TestEnvironment, null=True)

    objects = model_logic.ExtendedManager()

    def _get_attribute_model_and_args(self, attribute):
        return TestAttribute, dict(test=self, attribute=attribute,
                                   user_created=True)

    def set_attribute(self, attribute, value):
        # ensure non-user-created attributes remain immutable
        try:
            TestAttribute.objects.get(test=self, attribute=attribute,
                                      user_created=False)
            raise ValueError('Attribute %s already exists for test %s and is '
                             'immutable' % (attribute, self.test_idx))
        except TestAttribute.DoesNotExist:
            super(Test, self).set_attribute(attribute, value)

    class Meta:
        db_table = 'tko_tests'


class TestAttribute(dbmodels.Model, model_logic.ModelExtensions):
    test = dbmodels.ForeignKey(Test, db_column='test_idx')
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(blank=True, max_length=1024)
    user_created = dbmodels.BooleanField(default=False)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'tko_test_attributes'


class IterationAttribute(dbmodels.Model, model_logic.ModelExtensions):
    # this isn't really a primary key, but it's necessary to appease Django
    # and is harmless as long as we're careful
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(blank=True, max_length=300)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'tko_iteration_attributes'


class IterationResult(dbmodels.Model, model_logic.ModelExtensions):
    # see comment on IterationAttribute regarding primary_key=True
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.FloatField(null=True, blank=True)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'tko_iteration_result'


class TestLabel(dbmodels.Model, model_logic.ModelExtensions):
    name = dbmodels.CharField(max_length=80, unique=True)
    description = dbmodels.TextField(blank=True)
    tests = dbmodels.ManyToManyField(Test, blank=True,
                                     db_table='tko_test_labels_tests')

    name_field = 'name'
    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'tko_test_labels'


class SavedQuery(dbmodels.Model, model_logic.ModelExtensions):
    # TODO: change this to foreign key once DBs are merged
    owner = dbmodels.CharField(max_length=80)
    name = dbmodels.CharField(max_length=100)
    url_token = dbmodels.TextField()

    class Meta:
        db_table = 'tko_saved_queries'


class EmbeddedGraphingQuery(dbmodels.Model, model_logic.ModelExtensions):
    url_token = dbmodels.TextField(null=False, blank=False)
    graph_type = dbmodels.CharField(max_length=16, null=False, blank=False)
    params = dbmodels.TextField(null=False, blank=False)
    last_updated = dbmodels.DateTimeField(null=False, blank=False,
                                          editable=False)
    # refresh_time shows the time at which a thread is updating the cached
    # image, or NULL if no one is updating the image. This is used so that only
    # one thread is updating the cached image at a time (see
    # graphing_utils.handle_plot_request)
    refresh_time = dbmodels.DateTimeField(editable=False)
    cached_png = dbmodels.TextField(editable=False)

    class Meta:
        db_table = 'tko_embedded_graphing_queries'


# views

class TestViewManager(TempManager):

    def get_query_set(self):
        query = super(TestViewManager, self).get_query_set()

        # add extra fields to selects, using the SQL itself as the "alias"
        extra_select = dict((sql, sql)
                            for sql in self.model.extra_fields.iterkeys())
        return query.extra(select=extra_select)

    def _get_include_exclude_suffix(self, exclude):
        if exclude:
            return '_exclude'
        return '_include'

    def _add_attribute_join(self, query_set, join_condition,
                            suffix=None, exclude=False):
        if suffix is None:
            suffix = self._get_include_exclude_suffix(exclude)
        return self.add_join(query_set, 'tko_test_attributes',
                             join_key='test_idx',
                             join_condition=join_condition,
                             suffix=suffix, exclude=exclude)

    def _add_label_pivot_table_join(self, query_set, suffix, join_condition='',
                                    exclude=False, force_left_join=False):
        return self.add_join(query_set, 'tko_test_labels_tests',
                             join_key='test_id',
                             join_condition=join_condition,
                             suffix=suffix, exclude=exclude,
                             force_left_join=force_left_join)

    def _add_label_joins(self, query_set, suffix=''):
        query_set = self._add_label_pivot_table_join(
            query_set, suffix=suffix, force_left_join=True)

        # since we're not joining from the original table, we can't use
        # self.add_join() again
        second_join_alias = 'tko_test_labels' + suffix
        second_join_condition = ('%s.id = %s.testlabel_id' %
                                 (second_join_alias,
                                  'tko_test_labels_tests' + suffix))
        query_set.query.add_custom_join('tko_test_labels',
                                        second_join_condition,
                                        query_set.query.LOUTER,
                                        alias=second_join_alias)
        return query_set

    def _get_label_ids_from_names(self, label_names):
        label_ids = list(  # listifying avoids a double query below
            TestLabel.objects.filter(name__in=label_names)
            .values_list('name', 'id'))
        if len(label_ids) < len(set(label_names)):
            raise ValueError('Not all labels found: %s' %
                             ', '.join(label_names))
        return dict(name_and_id for name_and_id in label_ids)

    def _include_or_exclude_labels(self, query_set, label_names, exclude=False):
        label_ids = self._get_label_ids_from_names(label_names).itervalues()
        suffix = self._get_include_exclude_suffix(exclude)
        condition = ('tko_test_labels_tests%s.testlabel_id IN (%s)' %
                     (suffix,
                      ','.join(str(label_id) for label_id in label_ids)))
        return self._add_label_pivot_table_join(query_set,
                                                join_condition=condition,
                                                suffix=suffix,
                                                exclude=exclude)

    def _add_custom_select(self, query_set, select_name, select_sql):
        return query_set.extra(select={select_name: select_sql})

    def _add_select_value(self, query_set, alias):
        return self._add_custom_select(query_set, alias,
                                       _quote_name(alias) + '.value')

    def _add_select_ifnull(self, query_set, alias, non_null_value):
        select_sql = "IF(%s.id IS NOT NULL, '%s', NULL)" % (_quote_name(alias),
                                                            non_null_value)
        return self._add_custom_select(query_set, alias, select_sql)

    def _join_test_label_column(self, query_set, label_name, label_id):
        alias = 'test_label_' + label_name
        label_query = TestLabel.objects.filter(name=label_name)
        query_set = Test.objects.join_custom_field(query_set, label_query,
                                                   alias)

        query_set = self._add_select_ifnull(query_set, alias, label_name)
        return query_set

    def _join_test_label_columns(self, query_set, label_names):
        label_id_map = self._get_label_ids_from_names(label_names)
        for label_name in label_names:
            query_set = self._join_test_label_column(query_set, label_name,
                                                     label_id_map[label_name])
        return query_set

    def _join_test_attribute(self, query_set, attribute, alias=None,
                             extra_join_condition=None):
        """
        Join the given TestView QuerySet to TestAttribute.  The resulting query
        has an additional column for the given attribute named
        "attribute_<attribute name>".
        """
        if not alias:
            alias = 'test_attribute_' + attribute
        attribute_query = TestAttribute.objects.filter(attribute=attribute)
        if extra_join_condition:
            attribute_query = attribute_query.extra(
                where=[extra_join_condition])
        query_set = Test.objects.join_custom_field(query_set, attribute_query,
                                                   alias)

        query_set = self._add_select_value(query_set, alias)
        return query_set

    def _join_machine_label_columns(self, query_set, machine_label_names):
        for label_name in machine_label_names:
            alias = 'machine_label_' + label_name
            condition = "FIND_IN_SET('%s', %s)" % (
                label_name, _quote_name(alias) + '.value')
            query_set = self._join_test_attribute(
                query_set, 'host-labels',
                alias=alias, extra_join_condition=condition)
            query_set = self._add_select_ifnull(query_set, alias, label_name)
        return query_set

    def _join_one_iteration_key(self, query_set, result_key, first_alias=None):
        alias = 'iteration_result_' + result_key
        iteration_query = IterationResult.objects.filter(attribute=result_key)
        if first_alias:
            # after the first join, we need to match up iteration indices,
            # otherwise each join will expand the query by the number of
            # iterations and we'll have extraneous rows
            iteration_query = iteration_query.extra(
                where=['%s.iteration = %s.iteration'
                       % (_quote_name(alias), _quote_name(first_alias))])

        query_set = Test.objects.join_custom_field(query_set, iteration_query,
                                                   alias, left_join=False)
        # select the iteration value and index for this join
        query_set = self._add_select_value(query_set, alias)
        if not first_alias:
            # for first join, add iteration index select too
            query_set = self._add_custom_select(
                query_set, 'iteration_index',
                _quote_name(alias) + '.iteration')

        return query_set, alias

    def _join_iteration_results(self, test_view_query_set, result_keys):
        """Join the given TestView QuerySet to IterationResult for one result.

        The resulting query looks like a TestView query but has one row per
        iteration.  Each row includes all the attributes of TestView, an
        attribute for each key in result_keys and an iteration_index attribute.

        We accomplish this by joining the TestView query to IterationResult
        once per result key.  Each join is restricted on the result key (and on
        the test index, like all one-to-many joins).  For the first join, this
        is the only restriction, so each TestView row expands to a row per
        iteration (per iteration that includes the key, of course).  For each
        subsequent join, we also restrict the iteration index to match that of
        the initial join.  This makes each subsequent join produce exactly one
        result row for each input row.  (This assumes each iteration contains
        the same set of keys.  Results are undefined if that's not true.)
        """
        if not result_keys:
            return test_view_query_set

        query_set, first_alias = self._join_one_iteration_key(
            test_view_query_set, result_keys[0])
        for result_key in result_keys[1:]:
            query_set, _ = self._join_one_iteration_key(query_set, result_key,
                                                        first_alias=first_alias)
        return query_set

    def _join_job_keyvals(self, query_set, job_keyvals):
        for job_keyval in job_keyvals:
            alias = 'job_keyval_' + job_keyval
            keyval_query = JobKeyval.objects.filter(key=job_keyval)
            query_set = Job.objects.join_custom_field(query_set, keyval_query,
                                                      alias)
            query_set = self._add_select_value(query_set, alias)
        return query_set

    def _join_iteration_attributes(self, query_set, iteration_attributes):
        for attribute in iteration_attributes:
            alias = 'iteration_attribute_' + attribute
            attribute_query = IterationAttribute.objects.filter(
                attribute=attribute)
            query_set = Test.objects.join_custom_field(query_set,
                                                       attribute_query, alias)
            query_set = self._add_select_value(query_set, alias)
        return query_set

    def get_query_set_with_joins(self, filter_data):
        """
        Add joins for querying over test-related items.

        These parameters are supported going forward:
        * test_attribute_fields: list of attribute names.  Each attribute will
                be available as a column attribute_<name>.value.
        * test_label_fields: list of label names.  Each label will be available
                as a column label_<name>.id, non-null iff the label is present.
        * iteration_result_fields: list of iteration result names.  Each
                result will be available as a column iteration_<name>.value.
                Note that this changes the semantics to return iterations
                instead of tests -- if a test has multiple iterations, a row
                will be returned for each one.  The iteration index is also
                available as iteration_<name>.iteration.
        * machine_label_fields: list of machine label names.  Each will be
                available as a column machine_label_<name>.id, non-null iff the
                label is present on the machine used in the test.
        * job_keyval_fields: list of job keyval names. Each value will be
                available as a column job_keyval_<name>.id, non-null iff the
                keyval is present in the AFE job.
        * iteration_attribute_fields: list of iteration attribute names. Each
                attribute will be available as a column
                iteration_attribute<name>.id, non-null iff the attribute is
                present.

        These parameters are deprecated:
        * include_labels
        * exclude_labels
        * include_attributes_where
        * exclude_attributes_where

        Additionally, this method adds joins if the following strings are
        present in extra_where (this is also deprecated):
        * test_labels
        * test_attributes_host_labels
        """
        query_set = self.get_query_set()

        test_attributes = filter_data.pop('test_attribute_fields', [])
        for attribute in test_attributes:
            query_set = self._join_test_attribute(query_set, attribute)

        test_labels = filter_data.pop('test_label_fields', [])
        query_set = self._join_test_label_columns(query_set, test_labels)

        machine_labels = filter_data.pop('machine_label_fields', [])
        query_set = self._join_machine_label_columns(query_set, machine_labels)

        iteration_keys = filter_data.pop('iteration_result_fields', [])
        query_set = self._join_iteration_results(query_set, iteration_keys)

        job_keyvals = filter_data.pop('job_keyval_fields', [])
        query_set = self._join_job_keyvals(query_set, job_keyvals)

        iteration_attributes = filter_data.pop('iteration_attribute_fields', [])
        query_set = self._join_iteration_attributes(query_set,
                                                    iteration_attributes)

        # everything that follows is deprecated behavior

        joined = False

        extra_where = filter_data.get('extra_where', '')
        if 'tko_test_labels' in extra_where:
            query_set = self._add_label_joins(query_set)
            joined = True

        include_labels = filter_data.pop('include_labels', [])
        exclude_labels = filter_data.pop('exclude_labels', [])
        if include_labels:
            query_set = self._include_or_exclude_labels(query_set,
                                                        include_labels)
            joined = True
        if exclude_labels:
            query_set = self._include_or_exclude_labels(query_set,
                                                        exclude_labels,
                                                        exclude=True)
            joined = True

        include_attributes_where = filter_data.pop('include_attributes_where',
                                                   '')
        exclude_attributes_where = filter_data.pop('exclude_attributes_where',
                                                   '')
        if include_attributes_where:
            query_set = self._add_attribute_join(
                query_set,
                join_condition=self.escape_user_sql(include_attributes_where))
            joined = True
        if exclude_attributes_where:
            query_set = self._add_attribute_join(
                query_set,
                join_condition=self.escape_user_sql(exclude_attributes_where),
                exclude=True)
            joined = True

        if not joined:
            filter_data['no_distinct'] = True

        if 'tko_test_attributes_host_labels' in extra_where:
            query_set = self._add_attribute_join(
                query_set, suffix='_host_labels',
                join_condition='tko_test_attributes_host_labels.attribute = '
                               '"host-labels"')

        return query_set

    def query_test_ids(self, filter_data, apply_presentation=True):
        query = self.model.query_objects(filter_data,
                                         apply_presentation=apply_presentation)
        dicts = query.values('test_idx')
        return [item['test_idx'] for item in dicts]

    def query_test_label_ids(self, filter_data):
        query_set = self.model.query_objects(filter_data)
        query_set = self._add_label_joins(query_set, suffix='_list')
        rows = self._custom_select_query(query_set, ['tko_test_labels_list.id'])
        return [row[0] for row in rows if row[0] is not None]

    def escape_user_sql(self, sql):
        sql = super(TestViewManager, self).escape_user_sql(sql)
        return sql.replace('test_idx', self.get_key_on_this_table('test_idx'))


class TestView(dbmodels.Model, model_logic.ModelExtensions):
    extra_fields = {
        'DATE(job_queued_time)': 'job queued day',
        'DATE(test_finished_time)': 'test finished day',
    }

    group_fields = [
        'test_name',
        'status',
        'kernel',
        'hostname',
        'job_tag',
        'job_name',
        'platform',
        'reason',
        'job_owner',
        'job_queued_time',
        'DATE(job_queued_time)',
        'test_started_time',
        'test_finished_time',
        'DATE(test_finished_time)',
    ]

    test_idx = dbmodels.IntegerField('test index', primary_key=True)
    job_idx = dbmodels.IntegerField('job index', null=True, blank=True)
    test_name = dbmodels.CharField(blank=True, max_length=90)
    subdir = dbmodels.CharField('subdirectory', blank=True, max_length=180)
    kernel_idx = dbmodels.IntegerField('kernel index')
    status_idx = dbmodels.IntegerField('status index')
    reason = dbmodels.CharField(blank=True, max_length=3072)
    machine_idx = dbmodels.IntegerField('host index')
    test_started_time = dbmodels.DateTimeField(null=True, blank=True)
    test_finished_time = dbmodels.DateTimeField(null=True, blank=True)
    job_tag = dbmodels.CharField(blank=True, max_length=300)
    job_name = dbmodels.CharField(blank=True, max_length=300)
    job_owner = dbmodels.CharField('owner', blank=True, max_length=240)
    job_queued_time = dbmodels.DateTimeField(null=True, blank=True)
    job_started_time = dbmodels.DateTimeField(null=True, blank=True)
    job_finished_time = dbmodels.DateTimeField(null=True, blank=True)
    afe_job_id = dbmodels.IntegerField(null=True)
    hostname = dbmodels.CharField(blank=True, max_length=300)
    platform = dbmodels.CharField(blank=True, max_length=240)
    machine_owner = dbmodels.CharField(blank=True, max_length=240)
    kernel_hash = dbmodels.CharField(blank=True, max_length=105)
    kernel_base = dbmodels.CharField(blank=True, max_length=90)
    kernel = dbmodels.CharField(blank=True, max_length=300)
    status = dbmodels.CharField(blank=True, max_length=30)

    objects = TestViewManager()

    def save(self):
        raise NotImplementedError('TestView is read-only')

    def delete(self):
        raise NotImplementedError('TestView is read-only')

    @classmethod
    def query_objects(cls, filter_data, initial_query=None,
                      apply_presentation=True):
        if initial_query is None:
            initial_query = cls.objects.get_query_set_with_joins(filter_data)
        return super(TestView, cls).query_objects(
            filter_data, initial_query=initial_query,
            apply_presentation=apply_presentation)

    class Meta:
        db_table = 'tko_test_view_2'
        managed = False
