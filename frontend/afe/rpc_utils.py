"""\
Utility functions for rpc_interface.py.  We keep them in a separate file so that
only RPC interface functions go into that file.
"""

__author__ = 'showard@google.com (Steve Howard)'

import datetime, xmlrpclib, threading
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
    synch_count = max(test.sync_count for test in test_objects)
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

    # check for hosts that have only_if_needed labels that aren't requested
    labels_not_requested = models.Label.objects.filter(only_if_needed=True,
                                                       host__id__in=host_ids)
    labels_not_requested = labels_not_requested.exclude(
        name__in=job_dependencies)
    errors = []
    for label in labels_not_requested:
        hosts_in_label = hosts_in_job.filter(labels=label)
        errors.append('Cannot use hosts with label "%s" unless requested: %s' %
                      (label.name,
                       ', '.join(host.hostname for host in hosts_in_label)))
    if errors:
        raise model_logic.ValidationError({'hosts' : '\n'.join(errors)})


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
                    '(%d/%s, %d included, %d expected'
                    % (queue_entry.job.id, queue_entry.execution_subdir,
                       execution_subdir, queue_entry.job.synch_count)})
