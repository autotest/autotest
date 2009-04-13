"""\
Utility functions for rpc_interface.py.  We keep them in a separate file so that
only RPC interface functions go into that file.
"""

__author__ = 'showard@google.com (Steve Howard)'

import datetime, os
from frontend.afe import models, model_logic

NULL_DATETIME = datetime.datetime.max
NULL_DATE = datetime.date.max

def prepare_for_serialization(objects):
    """
    Prepare Python objects to be returned via RPC.
    """
    if (isinstance(objects, list) and len(objects) and
        isinstance(objects[0], dict) and 'id' in objects[0]):
        objects = gather_unique_dicts(objects)
    return _prepare_data(objects)


def prepare_rows_as_nested_dicts(query, nested_dict_column_names):
    """
    Prepare a Django query to be returned via RPC as a sequence of nested
    dictionaries.

    @param query - A Django model query object with a select_related() method.
    @param nested_dict_column_names - A list of column/attribute names for the
            rows returned by query to expand into nested dictionaries using
            their get_object_dict() method when not None.

    @returns An list suitable to returned in an RPC.
    """
    all_dicts = []
    for row in query.select_related():
        row_dict = row.get_object_dict()
        for column in nested_dict_column_names:
            if row_dict[column] is not None:
                row_dict[column] = getattr(row, column).get_object_dict()
        all_dicts.append(row_dict)
    return prepare_for_serialization(all_dicts)


def _prepare_data(data):
    """
    Recursively process data structures, performing necessary type
    conversions to values in data to allow for RPC serialization:
    -convert datetimes to strings
    -convert tuples and sets to lists
    """
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.iteritems():
            new_data[key] = _prepare_data(value)
        return new_data
    elif (isinstance(data, list) or isinstance(data, tuple) or
          isinstance(data, set)):
        return [_prepare_data(item) for item in data]
    elif isinstance(data, datetime.date):
        if data is NULL_DATETIME or data is NULL_DATE:
            return None
        return str(data)
    else:
        return data


def gather_unique_dicts(dict_iterable):
    """\
    Pick out unique objects (by ID) from an iterable of object dicts.
    """
    id_set = set()
    result = []
    for obj in dict_iterable:
        if obj['id'] not in id_set:
            id_set.add(obj['id'])
            result.append(obj)
    return result


def extra_job_filters(not_yet_run=False, running=False, finished=False):
    """\
    Generate a SQL WHERE clause for job status filtering, and return it in
    a dict of keyword args to pass to query.extra().  No more than one of
    the parameters should be passed as True.
    """
    assert not ((not_yet_run and running) or
                (not_yet_run and finished) or
                (running and finished)), ('Cannot specify more than one '
                                          'filter to this function')
    if not_yet_run:
        where = ['id NOT IN (SELECT job_id FROM host_queue_entries '
                 'WHERE active OR complete)']
    elif running:
        where = ['(id IN (SELECT job_id FROM host_queue_entries '
                  'WHERE active OR complete)) AND '
                 '(id IN (SELECT job_id FROM host_queue_entries '
                  'WHERE not complete OR active))']
    elif finished:
        where = ['id NOT IN (SELECT job_id FROM host_queue_entries '
                 'WHERE not complete OR active)']
    else:
        return None
    return {'where': where}


def extra_host_filters(multiple_labels=[]):
    """\
    Generate SQL WHERE clauses for matching hosts in an intersection of
    labels.
    """
    extra_args = {}
    where_str = ('hosts.id in (select host_id from hosts_labels '
                 'where label_id=%s)')
    extra_args['where'] = [where_str] * len(multiple_labels)
    extra_args['params'] = [models.Label.smart_get(label).id
                            for label in multiple_labels]
    return extra_args


def get_host_query(multiple_labels, exclude_only_if_needed_labels, filter_data):
    query = models.Host.valid_objects.all()
    if exclude_only_if_needed_labels:
        only_if_needed_labels = models.Label.valid_objects.filter(
            only_if_needed=True)
        if only_if_needed_labels.count() > 0:
            only_if_needed_ids = ','.join(str(label['id']) for label
                                          in only_if_needed_labels.values('id'))
            query = models.Host.objects.add_join(
                query, 'hosts_labels', join_key='host_id',
                join_condition='hosts_labels_exclude.label_id IN (%s)'
                               % only_if_needed_ids,
                suffix='_exclude', exclude=True)
    filter_data['extra_args'] = (extra_host_filters(multiple_labels))
    return models.Host.query_objects(filter_data, initial_query=query)


class InconsistencyException(Exception):
    'Raised when a list of objects does not have a consistent value'


def get_consistent_value(objects, field):
    if not objects:
        # well a list of nothing is consistent
        return None

    value = getattr(objects[0], field)
    for obj in objects:
        this_value = getattr(obj, field)
        if this_value != value:
            raise InconsistencyException(objects[0], obj)
    return value


def prepare_generate_control_file(tests, kernel, label, profilers):
    test_objects = [models.Test.smart_get(test) for test in tests]
    profiler_objects = [models.Profiler.smart_get(profiler)
                        for profiler in profilers]
    # ensure tests are all the same type
    try:
        test_type = get_consistent_value(test_objects, 'test_type')
    except InconsistencyException, exc:
        test1, test2 = exc.args
        raise model_logic.ValidationError(
            {'tests' : 'You cannot run both server- and client-side '
             'tests together (tests %s and %s differ' % (
            test1.name, test2.name)})

    is_server = (test_type == models.Test.Types.SERVER)
    if test_objects:
        synch_count = max(test.sync_count for test in test_objects)
    else:
        synch_count = 1
    if label:
        label = models.Label.smart_get(label)

    dependencies = set(label.name for label
                       in models.Label.objects.filter(test__in=test_objects))

    cf_info = dict(is_server=is_server, synch_count=synch_count,
                   dependencies=list(dependencies))
    return cf_info, test_objects, profiler_objects, label


def check_job_dependencies(host_objects, job_dependencies):
    """
    Check that a set of machines satisfies a job's dependencies.
    host_objects: list of models.Host objects
    job_dependencies: list of names of labels
    """
    # check that hosts satisfy dependencies
    host_ids = [host.id for host in host_objects]
    hosts_in_job = models.Host.objects.filter(id__in=host_ids)
    ok_hosts = hosts_in_job
    for index, dependency in enumerate(job_dependencies):
        ok_hosts &= models.Host.objects.filter_custom_join(
            '_label%d' % index, labels__name=dependency)
    failing_hosts = (set(host.hostname for host in host_objects) -
                     set(host.hostname for host in ok_hosts))
    if failing_hosts:
        raise model_logic.ValidationError(
            {'hosts' : 'Host(s) failed to meet job dependencies: ' +
                       ', '.join(failing_hosts)})


def _execution_key_for(host_queue_entry):
    return (host_queue_entry.job.id, host_queue_entry.execution_subdir)


def check_abort_synchronous_jobs(host_queue_entries):
    # ensure user isn't aborting part of a synchronous autoserv execution
    count_per_execution = {}
    for queue_entry in host_queue_entries:
        key = _execution_key_for(queue_entry)
        count_per_execution.setdefault(key, 0)
        count_per_execution[key] += 1

    for queue_entry in host_queue_entries:
        if not queue_entry.execution_subdir:
            continue
        execution_count = count_per_execution[_execution_key_for(queue_entry)]
        if execution_count < queue_entry.job.synch_count:
          raise model_logic.ValidationError(
              {'' : 'You cannot abort part of a synchronous job execution '
                    '(%d/%s), %d included, %d expected'
                    % (queue_entry.job.id, queue_entry.execution_subdir,
                       execution_count, queue_entry.job.synch_count)})


def check_atomic_group_create_job(synch_count, host_objects, metahost_objects,
                                  dependencies, atomic_group, labels_by_name):
    """
    Attempt to reject create_job requests with an atomic group that
    will be impossible to schedule.  The checks are not perfect but
    should catch the most obvious issues.

    @param synch_count - The job's minimum synch count.
    @param host_objects - A list of models.Host instances.
    @param metahost_objects - A list of models.Label instances.
    @param dependencies - A list of job dependency label names.
    @param atomic_group - The models.AtomicGroup instance.
    @param labels_by_name - A dictionary mapping label names to models.Label
            instance.  Used to look up instances for dependencies.

    @raises model_logic.ValidationError - When an issue is found.
    """
    # If specific host objects were supplied with an atomic group, verify
    # that there are enough to satisfy the synch_count.
    minimum_required = synch_count or 1
    if (host_objects and not metahost_objects and
        len(host_objects) < minimum_required):
        raise model_logic.ValidationError(
                {'hosts':
                 'only %d hosts provided for job with synch_count = %d' %
                 (len(host_objects), synch_count)})

    # Check that the atomic group has a hope of running this job
    # given any supplied metahosts and dependancies that may limit.

    # Get a set of hostnames in the atomic group.
    possible_hosts = set()
    for label in atomic_group.label_set.all():
        possible_hosts.update(h.hostname for h in label.host_set.all())

    # Filter out hosts that don't match all of the job dependency labels.
    for label_name in set(dependencies):
        label = labels_by_name[label_name]
        hosts_in_label = (h.hostname for h in label.host_set.all())
        possible_hosts.intersection_update(hosts_in_label)

    if not host_objects and not metahost_objects:
        # No hosts or metahosts are required to queue an atomic group Job.
        # However, if they are given, we respect them below.
        host_set = possible_hosts
    else:
        host_set = set(host.hostname for host in host_objects)
        unusable_host_set = host_set.difference(possible_hosts)
        if unusable_host_set:
            raise model_logic.ValidationError(
                {'hosts': 'Hosts "%s" are not in Atomic Group "%s"' %
                 (', '.join(sorted(unusable_host_set)), atomic_group.name)})

    # Lookup hosts provided by each meta host and merge them into the
    # host_set for final counting.
    for meta_host in metahost_objects:
        meta_possible = possible_hosts.copy()
        hosts_in_meta_host = (h.hostname for h in meta_host.host_set.all())
        meta_possible.intersection_update(hosts_in_meta_host)

        # Count all hosts that this meta_host will provide.
        host_set.update(meta_possible)

    if len(host_set) < minimum_required:
        raise model_logic.ValidationError(
                {'atomic_group_name':
                 'Insufficient hosts in Atomic Group "%s" with the'
                 ' supplied dependencies and meta_hosts.' %
                 (atomic_group.name,)})


def get_motd():
    dirname = os.path.dirname(__file__)
    filename = os.path.join(dirname, "..", "..", "motd.txt")
    text = ''
    try:
        fp = open(filename, "r")
        try:
            text = fp.read()
        finally:
            fp.close()
    except:
        pass

    return text
