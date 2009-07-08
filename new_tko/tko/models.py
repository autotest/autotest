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

        select_fields = [field for field in group_fields
                         if field not in extra_select_fields]
        for field_name, field_sql in extra_select_fields.iteritems():
            field_sql = self._get_key_unless_is_function(field_sql)
            select_fields.append(field_sql + ' AS ' + field_name)
            # add the extra fields to the query selects, so they'll be sortable
            # and Django won't mess with any of them
            query._select[field_name] = field_sql

        _, where, params = query._get_sql_clause()

        # insert GROUP BY clause into query
        group_by_clause = ' GROUP BY ' + ', '.join(group_fields)
        group_by_position = where.rfind('ORDER BY')
        if group_by_position == -1:
            group_by_position = len(where)
        where = (where[:group_by_position] +
                 group_by_clause + ' ' +
                 where[group_by_position:])

        return ('SELECT ' + ', '.join(select_fields) + where), params


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
        if query._distinct:
            pk_field = self.get_key_on_this_table()
            count_sql = 'COUNT(DISTINCT %s)' % pk_field
        else:
            count_sql = 'COUNT(1)'
        return self._GROUP_COUNT_NAME, count_sql


    def _get_num_groups_sql(self, query, group_by):
        group_fields = self._get_field_names(group_by)
        query._order_by = None # this can mess up the query and isn't needed
        _, where, params = query._get_sql_clause()
        return ('SELECT COUNT(DISTINCT %s) %s' % (','.join(group_fields),
                                                  where),
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
    hostname = dbmodels.CharField(unique=True, maxlength=300)
    machine_group = dbmodels.CharField(blank=True, maxlength=240)
    owner = dbmodels.CharField(blank=True, maxlength=240)

    class Meta:
        db_table = 'machines'


class Kernel(dbmodels.Model):
    kernel_idx = dbmodels.AutoField(primary_key=True)
    kernel_hash = dbmodels.CharField(maxlength=105, editable=False)
    base = dbmodels.CharField(maxlength=90)
    printable = dbmodels.CharField(maxlength=300)

    class Meta:
        db_table = 'kernels'


class Patch(dbmodels.Model):
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    name = dbmodels.CharField(blank=True, maxlength=240)
    url = dbmodels.CharField(blank=True, maxlength=900)
    hash_ = dbmodels.CharField(blank=True, maxlength=105, db_column='hash')

    class Meta:
        db_table = 'patches'


class Status(dbmodels.Model):
    status_idx = dbmodels.AutoField(primary_key=True)
    word = dbmodels.CharField(maxlength=30)

    class Meta:
        db_table = 'status'


class Job(dbmodels.Model):
    job_idx = dbmodels.AutoField(primary_key=True)
    tag = dbmodels.CharField(unique=True, maxlength=300)
    label = dbmodels.CharField(maxlength=300)
    username = dbmodels.CharField(maxlength=240)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    queued_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)
    finished_time = dbmodels.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'jobs'


class Test(dbmodels.Model, model_logic.ModelExtensions,
           model_logic.ModelWithAttributes):
    test_idx = dbmodels.AutoField(primary_key=True)
    job = dbmodels.ForeignKey(Job, db_column='job_idx')
    test = dbmodels.CharField(maxlength=90)
    subdir = dbmodels.CharField(blank=True, maxlength=180)
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    status = dbmodels.ForeignKey(Status, db_column='status')
    reason = dbmodels.CharField(blank=True, maxlength=3072)
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
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.CharField(blank=True, maxlength=300)
    user_created = dbmodels.BooleanField(default=False)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'test_attributes'


class IterationAttribute(dbmodels.Model, model_logic.ModelExtensions):
    # this isn't really a primary key, but it's necessary to appease Django
    # and is harmless as long as we're careful
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.CharField(blank=True, maxlength=300)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'iteration_attributes'


class IterationResult(dbmodels.Model, model_logic.ModelExtensions):
    # see comment on IterationAttribute regarding primary_key=True
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.FloatField(null=True, max_digits=12, decimal_places=31,
                              blank=True)

    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'iteration_result'


class TestLabel(dbmodels.Model, model_logic.ModelExtensions):
    name = dbmodels.CharField(maxlength=80, unique=True)
    description = dbmodels.TextField(blank=True)
    tests = dbmodels.ManyToManyField(Test, blank=True,
                                     filter_interface=dbmodels.HORIZONTAL)

    name_field = 'name'
    objects = model_logic.ExtendedManager()

    class Meta:
        db_table = 'test_labels'


class SavedQuery(dbmodels.Model, model_logic.ModelExtensions):
    # TODO: change this to foreign key once DBs are merged
    owner = dbmodels.CharField(maxlength=80)
    name = dbmodels.CharField(maxlength=100)
    url_token = dbmodels.TextField()

    class Meta:
        db_table = 'saved_queries'


class EmbeddedGraphingQuery(dbmodels.Model, model_logic.ModelExtensions):
    url_token = dbmodels.TextField(null=False, blank=False)
    graph_type = dbmodels.CharField(maxlength=16, null=False, blank=False)
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
            suffix = '_exclude'
        else:
            suffix = '_include'
        return suffix


    def _add_label_joins(self, query_set, suffix=''):
        query_set = self.add_join(query_set, 'test_labels_tests',
                                   join_key='test_id', suffix=suffix,
                                   force_left_join=True)

        second_join_alias = 'test_labels' + suffix
        second_join_condition = ('%s.id = %s.testlabel_id' %
                                 (second_join_alias,
                                  'test_labels_tests' + suffix))
        filter_object = self._CustomSqlQ()
        filter_object.add_join('test_labels',
                               second_join_condition,
                               'LEFT JOIN',
                               alias=second_join_alias)
        return query_set.filter(filter_object)


    def _add_attribute_join(self, query_set, join_condition='', suffix=None,
                            exclude=False):
        join_condition = self.escape_user_sql(join_condition)
        if suffix is None:
            suffix = self._get_include_exclude_suffix(exclude)
        return self.add_join(query_set, 'test_attributes',
                              join_key='test_idx',
                              join_condition=join_condition,
                              suffix=suffix, exclude=exclude)


    def _get_label_ids_from_names(self, label_names):
        if not label_names:
            return []
        query = TestLabel.objects.filter(name__in=label_names).values('id')
        return [str(label['id']) for label in query]


    def get_query_set_with_joins(self, filter_data, include_host_labels=False):
        include_labels = filter_data.pop('include_labels', [])
        exclude_labels = filter_data.pop('exclude_labels', [])
        query_set = self.get_query_set()
        joined = False
        # TODO: make this check more thorough if necessary
        extra_where = filter_data.get('extra_where', '')
        if 'test_labels' in extra_where:
            query_set = self._add_label_joins(query_set)
            joined = True

        include_label_ids = self._get_label_ids_from_names(include_labels)
        if include_label_ids:
            # TODO: Factor this out like what's done with attributes
            condition = ('test_labels_tests_include.testlabel_id IN (%s)' %
                         ','.join(include_label_ids))
            query_set = self.add_join(query_set, 'test_labels_tests',
                                       join_key='test_id',
                                       suffix='_include',
                                       join_condition=condition)
            joined = True

        exclude_label_ids = self._get_label_ids_from_names(exclude_labels)
        if exclude_label_ids:
            condition = ('test_labels_tests_exclude.testlabel_id IN (%s)' %
                         ','.join(exclude_label_ids))
            query_set = self.add_join(query_set, 'test_labels_tests',
                                       join_key='test_id',
                                       suffix='_exclude',
                                       join_condition=condition,
                                       exclude=True)
            joined = True

        include_attributes_where = filter_data.pop('include_attributes_where',
                                                   '')
        exclude_attributes_where = filter_data.pop('exclude_attributes_where',
                                                   '')
        if include_attributes_where:
            query_set = self._add_attribute_join(
                query_set, join_condition=include_attributes_where)
            joined = True
        if exclude_attributes_where:
            query_set = self._add_attribute_join(
                query_set, join_condition=exclude_attributes_where,
                exclude=True)
            joined = True

        if not joined:
            filter_data['no_distinct'] = True

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
    test_name = dbmodels.CharField(blank=True, maxlength=90)
    subdir = dbmodels.CharField('subdirectory', blank=True, maxlength=180)
    kernel_idx = dbmodels.IntegerField('kernel index')
    status_idx = dbmodels.IntegerField('status index')
    reason = dbmodels.CharField(blank=True, maxlength=3072)
    machine_idx = dbmodels.IntegerField('host index')
    test_started_time = dbmodels.DateTimeField(null=True, blank=True)
    test_finished_time = dbmodels.DateTimeField(null=True, blank=True)
    job_tag = dbmodels.CharField(blank=True, maxlength=300)
    job_name = dbmodels.CharField(blank=True, maxlength=300)
    job_owner = dbmodels.CharField('owner', blank=True, maxlength=240)
    job_queued_time = dbmodels.DateTimeField(null=True, blank=True)
    job_started_time = dbmodels.DateTimeField(null=True, blank=True)
    job_finished_time = dbmodels.DateTimeField(null=True, blank=True)
    hostname = dbmodels.CharField(blank=True, maxlength=300)
    platform = dbmodels.CharField(blank=True, maxlength=240)
    machine_owner = dbmodels.CharField(blank=True, maxlength=240)
    kernel_hash = dbmodels.CharField(blank=True, maxlength=105)
    kernel_base = dbmodels.CharField(blank=True, maxlength=90)
    kernel = dbmodels.CharField(blank=True, maxlength=300)
    status = dbmodels.CharField(blank=True, maxlength=30)

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
