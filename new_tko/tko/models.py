from django.db import models as dbmodels, connection
from django.utils import datastructures
from autotest_lib.frontend.afe import model_logic, readonly_connection

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
                field_names.append(field)
            else:
                field_names.append(self._get_key_unless_is_function(field))
        return field_names


    def _get_group_query_sql(self, query, group_by, extra_select_fields):
        group_fields = self._get_field_names(group_by, extra_select_fields)

        # Clone the queryset, so that we don't change the original
        query = query.all()

        # In order to use query.extra(), we need to first clear the limits
        # and then add them back in after the extra
        low = query.query.low_mark
        high = query.query.high_mark
        query.query.clear_limits()

        select_fields = dict(
            (field_name, self._get_key_unless_is_function(field_sql))
            for field_name, field_sql in extra_select_fields.iteritems())
        query = query.extra(select=select_fields)

        query.query.set_limits(low=low, high=high)

        sql, params = query.query.as_sql()

        # insert GROUP BY clause into query
        group_by_clause = ' GROUP BY ' + ', '.join(group_fields)
        group_by_position = sql.rfind('ORDER BY')
        if group_by_position == -1:
            group_by_position = len(sql)
        sql = (sql[:group_by_position] +
               group_by_clause + ' ' +
               sql[group_by_position:])

        return sql, params


    def _get_column_names(self, cursor):
        """\
        Gets the column names from the cursor description. This method exists
        so that it can be mocked in the unit test for sqlite3 compatibility."
        """
        return [column_info[0] for column_info in cursor.description]


    def execute_group_query(self, query, group_by, extra_select_fields=[]):
        """
        Performs the given query grouped by the fields in group_by with the
        given extra select fields added.  extra_select_fields should be a dict
        mapping field alias to field SQL.  Usually, the extra fields will use
        group aggregation functions.  Returns a list of dicts, where each dict
        corresponds to single row and contains a key for each grouped field as
        well as all of the extra select fields.
        """
        sql, params = self._get_group_query_sql(query, group_by,
                                                extra_select_fields)
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
        group_fields = self._get_field_names(group_by)
        query = query.order_by() # this can mess up the query and isn't needed

        sql, params = query.query.as_sql()
        from_ = sql[sql.find(' FROM'):]
        return ('SELECT COUNT(DISTINCT %s) %s' % (','.join(group_fields),
                                                  from_),
                params)


    def get_num_groups(self, query, group_by):
        """
        Returns the number of distinct groups for the given query grouped by the
        fields in group_by.
        """
        sql, params = self._get_num_groups_sql(query, group_by)
        cursor = readonly_connection.connection().cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


class Machine(dbmodels.Model):
    machine_idx = dbmodels.AutoField(primary_key=True)
    hostname = dbmodels.CharField(unique=True, max_length=300)
    machine_group = dbmodels.CharField(blank=True, max_length=240)
    owner = dbmodels.CharField(blank=True, max_length=240)

    class Meta:
        db_table = 'machines'


class Kernel(dbmodels.Model):
    kernel_idx = dbmodels.AutoField(primary_key=True)
    kernel_hash = dbmodels.CharField(max_length=105, editable=False)
    base = dbmodels.CharField(max_length=90)
    printable = dbmodels.CharField(max_length=300)

    class Meta:
        db_table = 'kernels'


class Patch(dbmodels.Model):
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    name = dbmodels.CharField(blank=True, max_length=240)
    url = dbmodels.CharField(blank=True, max_length=900)
    the_hash = dbmodels.CharField(blank=True, max_length=105, db_column='hash')

    class Meta:
        db_table = 'patches'


class Status(dbmodels.Model):
    status_idx = dbmodels.AutoField(primary_key=True)
    word = dbmodels.CharField(max_length=30)

    class Meta:
        db_table = 'status'


class Job(dbmodels.Model):
    job_idx = dbmodels.AutoField(primary_key=True)
    tag = dbmodels.CharField(unique=True, max_length=300)
    label = dbmodels.CharField(max_length=300)
    username = dbmodels.CharField(max_length=240)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    queued_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)
    finished_time = dbmodels.DateTimeField(null=True, blank=True)
    afe_job_id = dbmodels.IntegerField(null=True, default=None)

    class Meta:
        db_table = 'jobs'


class Test(dbmodels.Model, model_logic.ModelExtensions,
           model_logic.ModelWithAttributes):
    test_idx = dbmodels.AutoField(primary_key=True)
    job = dbmodels.ForeignKey(Job, db_column='job_idx')
    test = dbmodels.CharField(max_length=90)
    subdir = dbmodels.CharField(blank=True, max_length=180)
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    status = dbmodels.ForeignKey(Status, db_column='status')
    reason = dbmodels.CharField(blank=True, max_length=3072)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    finished_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)

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
        db_table = 'tests'


class TestAttribute(dbmodels.Model, model_logic.ModelExtensions):
    test = dbmodels.ForeignKey(Test, db_column='test_idx')
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(blank=True, max_length=300)
    user_created = dbmodels.BooleanField(default=False)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'test_attributes'


class IterationAttribute(dbmodels.Model, model_logic.ModelExtensions):
    # this isn't really a primary key, but it's necessary to appease Django
    # and is harmless as long as we're careful
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.CharField(blank=True, max_length=300)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'iteration_attributes'


class IterationResult(dbmodels.Model, model_logic.ModelExtensions):
    # see comment on IterationAttribute regarding primary_key=True
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(max_length=90)
    value = dbmodels.DecimalField(null=True, max_digits=12, decimal_places=31,
                                  blank=True)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'iteration_result'


class TestLabel(dbmodels.Model, model_logic.ModelExtensions):
    name = dbmodels.CharField(max_length=80, unique=True)
    description = dbmodels.TextField(blank=True)
    tests = dbmodels.ManyToManyField(Test, blank=True)

    name_field = 'name'
    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'test_labels'


class SavedQuery(dbmodels.Model, model_logic.ModelExtensions):
    # TODO: change this to foreign key once DBs are merged
    owner = dbmodels.CharField(max_length=80)
    name = dbmodels.CharField(max_length=100)
    url_token = dbmodels.TextField()

    class Meta:
        db_table = 'saved_queries'


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
        db_table = 'embedded_graphing_queries'


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
        return self.add_join(query_set, 'test_attributes', join_key='test_idx',
                             join_condition=join_condition,
                             suffix=suffix, exclude=exclude)


    def _add_label_pivot_table_join(self, query_set, suffix, join_condition='',
                                    exclude=False, force_left_join=False):
        return self.add_join(query_set, 'test_labels_tests', join_key='test_id',
                             join_condition=join_condition,
                             suffix=suffix, exclude=exclude,
                             force_left_join=force_left_join)


    def _add_label_joins(self, query_set, suffix=''):
        query_set = self._add_label_pivot_table_join(
                query_set, suffix=suffix, force_left_join=True)

        # since we're not joining from the original table, we can't use
        # self.add_join() again
        second_join_alias = 'test_labels' + suffix
        second_join_condition = ('%s.id = %s.testlabel_id' %
                                 (second_join_alias,
                                  'test_labels_tests' + suffix))
        filter_object = self._CustomSqlQ()
        filter_object.add_join('test_labels',
                               second_join_condition,
                               query_set.query.LOUTER,
                               alias=second_join_alias)
        return self._add_customSqlQ(query_set, filter_object)


    def _get_label_ids_from_names(self, label_names):
        assert label_names
        label_ids = list( # listifying avoids a double query below
                TestLabel.objects.filter(name__in=label_names).values('id'))
        if len(label_ids) < len(set(label_names)):
                raise ValueError('Not all labels found: %s' %
                                 ', '.join(label_names))
        return [str(label['id']) for label in label_ids]


    def _include_or_exclude_labels(self, query_set, label_names, exclude=False):
        label_ids = self._get_label_ids_from_names(label_names)
        suffix = self._get_include_exclude_suffix(exclude)
        condition = ('test_labels_tests%s.testlabel_id IN (%s)' %
                     (suffix, ','.join(label_ids)))
        return self._add_label_pivot_table_join(query_set,
                                                join_condition=condition,
                                                suffix=suffix,
                                                exclude=exclude)


    def get_query_set_with_joins(self, filter_data, include_host_labels=False):
        include_labels = filter_data.pop('include_labels', [])
        exclude_labels = filter_data.pop('exclude_labels', [])
        query_set = self.get_query_set()
        joined = False

        # TODO: make this feature obsolete in favor of include_labels and
        # exclude_labels
        extra_where = filter_data.get('extra_where', '')
        if 'test_labels' in extra_where:
            query_set = self._add_label_joins(query_set)
            joined = True

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

        # TODO: make test_attributes_host_labels obsolete too
        if include_host_labels or 'test_attributes_host_labels' in extra_where:
            query_set = self._add_attribute_join(
                query_set, suffix='_host_labels',
                join_condition='test_attributes_host_labels.attribute = '
                               '"host-labels"')

        return query_set


    def query_test_ids(self, filter_data):
        dicts = self.model.query_objects(filter_data).values('test_idx')
        return [item['test_idx'] for item in dicts]


    def query_test_label_ids(self, filter_data):
        query_set = self.model.query_objects(filter_data)
        query_set = self._add_label_joins(query_set, suffix='_list')
        rows = self._custom_select_query(query_set, ['test_labels_list.id'])
        return [row[0] for row in rows if row[0] is not None]


    def escape_user_sql(self, sql):
        sql = super(TestViewManager, self).escape_user_sql(sql)
        return sql.replace('test_idx', self.get_key_on_this_table('test_idx'))


    def _join_one_iteration_key(self, query_set, result_key, index):
        suffix = '_%s' % index
        table_name = IterationResult._meta.db_table
        alias = table_name + suffix
        condition_parts = ["%s.attribute = '%s'" %
                           (alias, self.escape_user_sql(result_key))]
        if index > 0:
            # after the first join, we need to match up iteration indices,
            # otherwise each join will expand the query by the number of
            # iterations and we'll have extraneous rows
            first_alias = table_name + '_0'
            condition_parts.append('%s.iteration = %s.iteration' %
                                   (alias, first_alias))

        condition = ' and '.join(condition_parts)
        # add a join to IterationResult
        query_set = self.add_join(query_set, table_name, join_key='test_idx',
                                  join_condition=condition, suffix=suffix)
        # select the iteration value for this join
        query_set = query_set.extra(select={result_key: '%s.value' % alias})
        if index == 0:
            # pull the iteration index from the first join
            query_set = query_set.extra(
                    select={'iteration_index': '%s.iteration' % alias})

        return query_set


    def join_iterations(self, test_view_query_set, result_keys):
        """
        Join the given TestView QuerySet to IterationResult.  The resulting
        query looks like a TestView query but has one row per iteration.  Each
        row includes all the attributes of TestView, an attribute for each key
        in result_keys and an iteration_index attribute.

        We accomplish this by joining the TestView query to IterationResult
        once per result key.  Each join is restricted on the result key (and on
        the test index, like all one-to-many joins).  For the first join, this
        is the only restriction, so each TestView row expands to a row per
        iteration (per iteration that includes the key, of course).  For each
        subsequent join, we also restrict the iteration index to match that of
        the initial join.  This makes each subsequent join produce exactly one
        result row for each input row.  (This assumes each iteration contains
        the same set of keys.)
        """
        query_set = test_view_query_set
        for index, result_key in enumerate(result_keys):
            query_set = self._join_one_iteration_key(query_set, result_key,
                                                     index)
        return query_set


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
    def query_objects(cls, filter_data, initial_query=None):
        if initial_query is None:
            initial_query = cls.objects.get_query_set_with_joins(filter_data)
        return super(TestView, cls).query_objects(filter_data,
                                                  initial_query=initial_query)


    @classmethod
    def list_objects(cls, filter_data, initial_query=None, fields=None):
        # include extra fields
        if fields is None:
            fields = cls.get_field_dict().keys() + cls.extra_fields.keys()
        return super(TestView, cls).list_objects(filter_data, initial_query,
                                                 fields)


    class Meta:
        db_table = 'test_view_2'
