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

        # add the count field and all group fields to the query selects, so
        # they'll be sortable and Django won't mess with any of them
        #for field in group_fields + [self._GROUP_COUNT_NAME]:
        #    query._select[field] = ''
        query._select[self._GROUP_COUNT_NAME] = count_sql

        # Inject the GROUP_BY clause into the query by adding it to the end of
        # the queries WHERE clauses. We need it to come before the ORDER BY and
        # LIMIT clauses.
        num_real_where_clauses = len(query._where)
        query._where.append('GROUP BY ' + ', '.join(group_fields))
        _, where, params = query._get_sql_clause()
        if num_real_where_clauses == 0:
            # handle the special case where there were no actual WHERE clauses
            where = where.replace('WHERE GROUP BY', 'GROUP BY')
        else:
            where = where.replace('AND GROUP BY', 'GROUP BY')

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


class TestManager(dbmodels.Manager):
    'Custom manager for Test model'
    def query_using_test_view(self, filter_data):
        test_ids = [test_view.test_idx for test_view
                    in TestView.query_objects(filter_data)]
        return self.in_bulk(test_ids).values()


class Test(dbmodels.Model):
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

    objects = TestManager()

    class Meta:
        db_table = 'tests'


class TestAttribute(dbmodels.Model):
    test = dbmodels.ForeignKey(Test, db_column='test_idx')
    attribute = dbmodels.CharField(maxlength=90)
    value = dbmodels.CharField(blank=True, maxlength=300)

    class Meta:
        db_table = 'test_attributes'


class IterationAttribute(dbmodels.Model):
    test = dbmodels.ForeignKey(Test, db_column='test_idx')
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
    name = dbmodels.CharField(maxlength=80)
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


# views

class TestViewManager(TempManager):
    class _JoinQ(dbmodels.Q):
        def __init__(self):
            self._joins = datastructures.SortedDict()


        def add_join(self, table, condition, join_type, alias=None):
            if alias is None:
                alias = table
            self._joins[alias] = (table, join_type, condition)


        def get_sql(self, opts):
            return self._joins, [], []


    def get_query_set(self):
        query = super(TestViewManager, self).get_query_set()
        
        # add extra fields to selects, using the SQL itself as the "alias"
        extra_select = dict((sql, sql)
                            for sql in self.model.extra_fields.iterkeys())
        return query.extra(select=extra_select)


    def get_query_set_with_labels(self, filter_data):
        query_set = self.get_query_set()
        # TODO: make this check more thorough if necessary
        if 'test_labels' in filter_data.get('extra_where', ''):
            filter_object = self._JoinQ()
            filter_object.add_join(
                'test_labels_tests',
                'test_labels_tests.test_id = test_view.test_idx',
                'LEFT JOIN')
            filter_object.add_join(
                'test_labels',
                'test_labels.id = test_labels_tests.testlabel_id',
                'LEFT JOIN')
            query_set = query_set.complex_filter(filter_object).distinct()
        else:
            filter_data['no_distinct'] = True
        return query_set


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
            initial_query = cls.objects.get_query_set_with_labels(filter_data)
        return super(TestView, cls).query_objects(filter_data,
                                                  initial_query=initial_query)


    @classmethod
    def list_objects(cls, filter_data, initial_query=None):
        """
        Django's ValuesQuerySet (used when you call query.values()) doesn't
        support custom select fields, so we have to basically reimplement it
        here.
        TODO: merge this up to ModelExtensions after some settling time.
        """
        query = cls.query_objects(filter_data, initial_query=initial_query)
        object_dicts = []
        for model_object in query:
            object_dict = model_object.get_object_dict()
            for sql in cls.extra_fields.iterkeys():
                object_dict[sql] = getattr(model_object, sql)
            object_dicts.append(object_dict)
        return object_dicts


    class Meta:
        db_table = 'test_view_2'
