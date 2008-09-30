from django.db import models as dbmodels, connection
from django.utils import datastructures
from autotest_lib.frontend.afe import model_logic, readonly_connection

class TempManager(model_logic.ExtendedManager):
    _GROUP_COUNT_NAME = 'group_count'

    def _get_key_unless_is_function(self, field):
        if '(' in field:
            return field
        return self._get_key_on_this_table(field)


    def _get_field_names(self, fields):
        return [self._get_key_unless_is_function(field) for field in fields]


    def _get_group_query_sql(self, query, group_by, extra_select_fields):
        group_fields = self._get_field_names(group_by)
        if query._distinct:
            pk_field = self._get_key_on_this_table(self.model._meta.pk.name)
            count_sql = 'COUNT(DISTINCT %s)' % pk_field
        else:
            count_sql = 'COUNT(1)'
        select_fields = (group_fields +
                         [count_sql + ' AS ' + self._GROUP_COUNT_NAME] +
                         extra_select_fields)

        # add the count field to the query selects, so they'll be sortable and
        # Django won't mess with any of them
        query._select[self._GROUP_COUNT_NAME] = count_sql

        _, where, params = query._get_sql_clause()

        # insert GROUP BY clause into query
        group_by_clause = 'GROUP BY ' + ', '.join(group_fields)
        group_by_position = where.rfind('ORDER BY')
        if group_by_position == -1:
            group_by_position = len(where)
        where = (where[:group_by_position] +
                 group_by_clause + ' ' +
                 where[group_by_position:])

        return ('SELECT ' + ', '.join(select_fields) + where), params


    def get_group_counts(self, query, group_by, extra_select_fields=[]):
        """
        Performs the given query grouped by the fields in group_by.  Returns a
        list of rows, where each row is a list containing the value of each
        field in group_by, followed by the group count.
        """
        sql, params = self._get_group_query_sql(query, group_by,
                                                extra_select_fields)
        cursor = readonly_connection.connection.cursor()
        num_rows = cursor.execute(sql, params)
        return cursor.fetchall()


    def _get_num_groups_sql(self, query, group_by):
        group_fields = self._get_field_names(group_by)
        query._order_by = None # this can mess up the query is isn't needed
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
        cursor = readonly_connection.connection.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


class Machine(dbmodels.Model):
    machine_idx = dbmodels.IntegerField(primary_key=True)
    hostname = dbmodels.CharField(unique=True, maxlength=300)
    machine_group = dbmodels.CharField(blank=True, maxlength=240)
    owner = dbmodels.CharField(blank=True, maxlength=240)

    class Meta:
        db_table = 'machines'


class Kernel(dbmodels.Model):
    kernel_idx = dbmodels.IntegerField(primary_key=True)
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
    status_idx = dbmodels.IntegerField(primary_key=True)
    word = dbmodels.CharField(maxlength=30)

    class Meta:
        db_table = 'status'


class Job(dbmodels.Model):
    job_idx = dbmodels.IntegerField(primary_key=True)
    tag = dbmodels.CharField(unique=True, maxlength=300)
    label = dbmodels.CharField(maxlength=300)
    username = dbmodels.CharField(maxlength=240)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    queued_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)
    finished_time = dbmodels.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'jobs'


class Test(dbmodels.Model, model_logic.ModelExtensions):
    test_idx = dbmodels.IntegerField(primary_key=True)
    job = dbmodels.ForeignKey(Job, db_column='job_idx')
    test = dbmodels.CharField(maxlength=90)
    subdir = dbmodels.CharField(blank=True, maxlength=180)
    kernel = dbmodels.ForeignKey(Kernel, db_column='kernel_idx')
    status = dbmodels.ForeignKey(Status, db_column='status')
    reason = dbmodels.CharField(blank=True, maxlength=3072)
    machine = dbmodels.ForeignKey(Machine, db_column='machine_idx')
    finished_time = dbmodels.DateTimeField(null=True, blank=True)
    started_time = dbmodels.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tests'


class TestAttribute(dbmodels.Model, model_logic.ModelExtensions):
    # this isn't really a primary key, but it's necessary to appease Django
    # and is harmless as long as we're careful
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.CharField(blank=True, maxlength=300)

    class Meta:
        db_table = 'test_attributes'


class IterationAttribute(dbmodels.Model):
    # see comment on TestAttribute regarding primary_key=True
    test = dbmodels.ForeignKey(Test, db_column='test_idx', primary_key=True)
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.CharField(blank=True, maxlength=300)

    class Meta:
        db_table = 'iteration_attributes'


class IterationResult(dbmodels.Model):
    test = dbmodels.ForeignKey(Test, db_column='test_idx')
    iteration = dbmodels.IntegerField()
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.FloatField(null=True, max_digits=12, decimal_places=31,
                              blank=True)

    class Meta:
        db_table = 'iteration_result'


class TestLabel(dbmodels.Model, model_logic.ModelExtensions):
    name = dbmodels.CharField(maxlength=80, unique=True)
    description = dbmodels.TextField(blank=True)
    tests = dbmodels.ManyToManyField(Test, blank=True,
                                     filter_interface=dbmodels.HORIZONTAL)

    name_field = 'name'

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
    class _CustomSqlQ(dbmodels.Q):
        def __init__(self):
            self._joins = datastructures.SortedDict()
            self._where, self._params = [], []


        def add_join(self, table, condition, join_type, alias=None):
            if alias is None:
                alias = table
            condition = condition.replace('%', '%%')
            self._joins[alias] = (table, join_type, condition)


        def add_where(self, where, params=[]):
            self._where.append(where)
            self._params.extend(params)


        def get_sql(self, opts):
            return self._joins, self._where, self._params


    def get_query_set(self):
        query = super(TestViewManager, self).get_query_set()

        # add extra fields to selects, using the SQL itself as the "alias"
        extra_select = dict((sql, sql)
                            for sql in self.model.extra_fields.iterkeys())
        return query.extra(select=extra_select)


    def _add_join(self, query_set, join_table, join_condition='',
                  join_key='test_idx', suffix='', exclude=False,
                  force_left_join=False):
        table_name = self.model._meta.db_table
        join_alias = join_table + suffix
        full_join_key = join_alias + '.' + join_key
        full_join_condition = '%s = %s.test_idx' % (full_join_key, table_name)
        if join_condition:
            full_join_condition += ' AND (' + join_condition + ')'
        if exclude or force_left_join:
            join_type = 'LEFT JOIN'
        else:
            join_type = 'INNER JOIN'

        filter_object = self._CustomSqlQ()
        filter_object.add_join(join_table,
                               full_join_condition,
                               join_type,
                               alias=join_alias)
        if exclude:
            filter_object.add_where(full_join_key + ' IS NULL')
        return query_set.filter(filter_object).distinct()


    def _add_label_joins(self, query_set, suffix=''):
        query_set = self._add_join(query_set, 'test_labels_tests',
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


    def _add_attribute_join(self, query_set, suffix='', join_condition='',
                            exclude=False):
        return self._add_join(query_set, 'test_attributes',
                              join_condition=join_condition,
                              suffix=suffix, exclude=exclude)


    def _get_label_ids_from_names(self, label_names):
        if not label_names:
            return []
        query = TestLabel.objects.filter(name__in=label_names).values('id')
        return [label['id'] for label in query]


    def get_query_set_with_joins(self, filter_data):
        exclude_labels = filter_data.pop('exclude_labels', [])
        query_set = self.get_query_set()
        joined = False
        # TODO: make this check more thorough if necessary
        if 'test_labels' in filter_data.get('extra_where', ''):
            query_set = self._add_label_joins(query_set)
            joined = True

        exclude_label_ids = self._get_label_ids_from_names(exclude_labels)
        if exclude_label_ids:
            condition = ('test_labels_tests_exclude.testlabel_id IN (%s)' %
                         ','.join(str(label_id)
                                  for label_id in exclude_label_ids))
            query_set = self._add_join(query_set, 'test_labels_tests',
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
                query_set, suffix='_include',
                join_condition=include_attributes_where)
            joined = True
        if exclude_attributes_where:
            query_set = self._add_attribute_join(
                query_set, suffix='_exclude',
                join_condition=exclude_attributes_where,
                exclude=True)
            joined = True

        if not joined:
            filter_data['no_distinct'] = True

        return query_set


    def query_test_ids(self, filter_data):
        dicts = self.model.query_objects(filter_data).values('test_idx')
        return [item['test_idx'] for item in dicts]


    def _custom_select_query(self, query_set, selects):
        query_selects, where, params = query_set._get_sql_clause()
        if query_set._distinct:
            distinct = 'DISTINCT '
        else:
            distinct = ''
        sql_query = 'SELECT ' + distinct + ','.join(selects) + where
        cursor = readonly_connection.connection.cursor()
        cursor.execute(sql_query, params)
        return cursor.fetchall()


    def query_test_label_ids(self, filter_data):
        query_set = self.model.query_objects(filter_data)
        query_set = self._add_label_joins(query_set, suffix='_list')
        rows = self._custom_select_query(query_set, ['test_labels_list.id'])
        return [row[0] for row in rows if row[0] is not None]


class TestView(dbmodels.Model, model_logic.ModelExtensions):
    extra_fields = {
        'DATE(test_finished_time)' : 'test finished day',
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
