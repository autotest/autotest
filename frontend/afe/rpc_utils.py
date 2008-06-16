"""\
Utility functions for rpc_interface.py.  We keep them in a separate file so that
only RPC interface functions go into that file.
"""

__author__ = 'showard@google.com (Steve Howard)'

import datetime, xmlrpclib, threading
from frontend.afe import models, model_logic

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
    elif isinstance(data, datetime.datetime):
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


local_vars = threading.local()

def set_user(user):
    """\
    Sets the current request's logged-in user.  user should be a
    afe.models.User object.
    """
    local_vars.user = user


def get_user():
    'Get the currently logged-in user as a afe.models.User object.'
    return local_vars.user


class InconsistencyException(Exception):
    'Raised when a list of objects does not have a consistent value'


def get_consistent_value(objects, field):
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

    try:
        synch_type = get_consistent_value(test_objects, 'synch_type')
    except InconsistencyException, exc:
        test1, test2 = exc.args
        raise model_logic.ValidationError(
            {'tests' : 'You cannot run both synchronous and '
             'asynchronous tests together (tests %s and %s differ)' % (
            test1.name, test2.name)})

    is_server = (test_type == models.Test.Types.SERVER)
    is_synchronous = (synch_type == models.Test.SynchType.SYNCHRONOUS)
    if label:
        label = models.Label.smart_get(label)

    return is_server, is_synchronous, test_objects, profiler_objects, label
