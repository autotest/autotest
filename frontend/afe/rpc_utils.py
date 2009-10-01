"""\
Utility functions for rpc_interface.py.  We keep them in a separate file so that
only RPC interface functions go into that file.
"""

__author__ = 'showard@google.com (Steve Howard)'

import datetime, os
import django.http
from autotest_lib.frontend.afe import models, model_logic

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


def raw_http_response(response_data, content_type=None):
    response = django.http.HttpResponse(response_data, mimetype=content_type)
    response['Content-length'] = str(len(response.content))
    return response


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
    * not_yet_run: all HQEs are Queued
    * finished: all HQEs are complete
    * running: everything else
    """
    assert not ((not_yet_run and running) or
                (not_yet_run and finished) or
                (running and finished)), ('Cannot specify more than one '
                                          'filter to this function')

    not_queued = ('(SELECT job_id FROM host_queue_entries WHERE status != "%s")'
                  % models.HostQueueEntry.Status.QUEUED)
    not_finished = '(SELECT job_id FROM host_queue_entries WHERE not complete)'

    if not_yet_run:
        where = ['id NOT IN ' + not_queued]
    elif running:
        where = ['(id IN %s) AND (id IN %s)' % (not_queued, not_finished)]
    elif finished:
        where = ['id NOT IN ' + not_finished]
    else:
        return {}
    return {'where': where}


def extra_host_filters(multiple_labels=()):
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


def get_host_query(multiple_labels, exclude_only_if_needed_labels,
                   exclude_atomic_group_hosts, valid_only, filter_data):
    if valid_only:
        query = models.Host.valid_objects.all()
    else:
        query = models.Host.objects.all()

    if exclude_only_if_needed_labels:
        only_if_needed_labels = models.Label.valid_objects.filter(
            only_if_needed=True)
        if only_if_needed_labels.count() > 0:
            only_if_needed_ids = ','.join(
                    str(label['id'])
                    for label in only_if_needed_labels.values('id'))
            query = models.Host.objects.add_join(
                query, 'hosts_labels', join_key='host_id',
                join_condition=('hosts_labels_exclude_OIN.label_id IN (%s)'
                                % only_if_needed_ids),
                suffix='_exclude_OIN', exclude=True)

    if exclude_atomic_group_hosts:
        atomic_group_labels = models.Label.valid_objects.filter(
                atomic_group__isnull=False)
        if atomic_group_labels.count() > 0:
            atomic_group_label_ids = ','.join(
                    str(atomic_group['id'])
                    for atomic_group in atomic_group_labels.values('id'))
            query = models.Host.objects.add_join(
                    query, 'hosts_labels', join_key='host_id',
                    join_condition=('hosts_labels_exclude_AG.label_id IN (%s)'
                                    % atomic_group_label_ids),
                    suffix='_exclude_AG', exclude=True)

    assert 'extra_args' not in filter_data
    filter_data['extra_args'] = extra_host_filters(multiple_labels)
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
        ok_hosts = ok_hosts.filter(labels__name=dependency)
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


def check_modify_host(update_data):
    """
    Sanity check modify_host* requests.

    @param update_data: A dictionary with the changes to make to a host
            or hosts.
    """
    # Only the scheduler (monitor_db) is allowed to modify Host status.
    # Otherwise race conditions happen as a hosts state is changed out from
    # beneath tasks being run on a host.
    if 'status' in update_data:
        raise model_logic.ValidationError({
                'status': 'Host status can not be modified by the frontend.'})


def check_modify_host_locking(host, update_data):
    """
    Checks when locking/unlocking has been requested if the host is already
    locked/unlocked.

    @param host: models.Host object to be modified
    @param update_data: A dictionary with the changes to make to the host.
    """
    locked = update_data.get('locked', None)
    if locked is not None:
        if locked and host.locked:
            raise model_logic.ValidationError({
                    'locked': 'Host already locked by %s on %s.' %
                    (host.locked_by, host.lock_time)})
        if not locked and not host.locked:
            raise model_logic.ValidationError({
                    'locked': 'Host already unlocked.'})


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


def _get_metahost_counts(metahost_objects):
    metahost_counts = {}
    for metahost in metahost_objects:
        metahost_counts.setdefault(metahost, 0)
        metahost_counts[metahost] += 1
    return metahost_counts


def get_job_info(job, preserve_metahosts=False, queue_entry_filter_data=None):
    hosts = []
    one_time_hosts = []
    meta_hosts = []
    atomic_group = None

    queue_entries = job.hostqueueentry_set.all()
    if queue_entry_filter_data:
        queue_entries = models.HostQueueEntry.query_objects(
            queue_entry_filter_data, initial_query=queue_entries)

    for queue_entry in queue_entries:
        if (queue_entry.host and (preserve_metahosts or
                                  not queue_entry.meta_host)):
            if queue_entry.deleted:
                continue
            if queue_entry.host.invalid:
                one_time_hosts.append(queue_entry.host)
            else:
                hosts.append(queue_entry.host)
        else:
            meta_hosts.append(queue_entry.meta_host)
        if atomic_group is None:
            if queue_entry.atomic_group is not None:
                atomic_group = queue_entry.atomic_group
        else:
            assert atomic_group.name == queue_entry.atomic_group.name, (
                    'DB inconsistency.  HostQueueEntries with multiple atomic'
                    ' groups on job %s: %s != %s' % (
                        id, atomic_group.name, queue_entry.atomic_group.name))

    meta_host_counts = _get_metahost_counts(meta_hosts)

    info = dict(dependencies=[label.name for label
                              in job.dependency_labels.all()],
                hosts=hosts,
                meta_hosts=meta_hosts,
                meta_host_counts=meta_host_counts,
                one_time_hosts=one_time_hosts,
                atomic_group=atomic_group)
    return info


def create_new_job(owner, options, host_objects, metahost_objects,
                   atomic_group=None):
    labels_by_name = dict((label.name, label)
                          for label in models.Label.objects.all())
    all_host_objects = host_objects + metahost_objects
    metahost_counts = _get_metahost_counts(metahost_objects)
    dependencies = options.get('dependencies', [])
    synch_count = options.get('synch_count')

    # check that each metahost request has enough hosts under the label
    for label, requested_count in metahost_counts.iteritems():
        available_count = label.host_set.count()
        if requested_count > available_count:
            error = ("You have requested %d %s's, but there are only %d."
                     % (requested_count, label.name, available_count))
            raise model_logic.ValidationError({'meta_hosts' : error})

    if atomic_group:
        check_atomic_group_create_job(
                synch_count, host_objects, metahost_objects,
                dependencies, atomic_group, labels_by_name)
    else:
        if synch_count is not None and synch_count > len(all_host_objects):
            raise model_logic.ValidationError(
                    {'hosts':
                     'only %d hosts provided for job with synch_count = %d' %
                     (len(all_host_objects), synch_count)})
        atomic_hosts = models.Host.objects.filter(
                id__in=[host.id for host in host_objects],
                labels__atomic_group=True)
        unusable_host_names = [host.hostname for host in atomic_hosts]
        if unusable_host_names:
            raise model_logic.ValidationError(
                    {'hosts':
                     'Host(s) "%s" are atomic group hosts but no '
                     'atomic group was specified for this job.' %
                     (', '.join(unusable_host_names),)})


    check_job_dependencies(host_objects, dependencies)
    options['dependencies'] = [labels_by_name[label_name]
                               for label_name in dependencies]

    for label in metahost_objects + options['dependencies']:
        if label.atomic_group and not atomic_group:
            raise model_logic.ValidationError(
                    {'atomic_group_name':
                     'Dependency %r requires an atomic group but no '
                     'atomic_group_name or meta_host in an atomic group was '
                     'specified for this job.' % label.name})
        elif (label.atomic_group and
              label.atomic_group.name != atomic_group.name):
            raise model_logic.ValidationError(
                    {'atomic_group_name':
                     'meta_hosts or dependency %r requires atomic group '
                     '%r instead of the supplied atomic_group_name=%r.' %
                     (label.name, label.atomic_group.name, atomic_group.name)})

    job = models.Job.create(owner=owner, options=options,
                            hosts=all_host_objects)
    job.queue(all_host_objects, atomic_group=atomic_group,
              is_template=options.get('is_template', False))
    return job.id


def find_platform_and_atomic_group(host):
    """
    Figure out the platform name and atomic group name for the given host
    object.  If none, the return value for either will be None.

    @returns (platform name, atomic group name) for the given host.
    """
    platforms = [label.name for label in host.label_list if label.platform]
    if not platforms:
        platform = None
    else:
        platform = platforms[0]
    if len(platforms) > 1:
        raise ValueError('Host %s has more than one platform: %s' %
                         (host.hostname, ', '.join(platforms)))
    for label in host.label_list:
        if label.atomic_group:
            atomic_group_name = label.atomic_group.name
            break
    else:
        atomic_group_name = None
    # Don't check for multiple atomic groups on a host here.  That is an
    # error but should not trip up the RPC interface.  monitor_db_cleanup
    # deals with it.  This just returns the first one found.
    return platform, atomic_group_name


# support for get_host_queue_entries_and_special_tasks()

def _common_entry_to_dict(entry, type, job_dict):
    return dict(type=type,
                host=entry.host.get_object_dict(),
                job=job_dict,
                execution_path=entry.execution_path(),
                status=entry.status,
                started_on=entry.started_on,
                id=str(entry.id) + type)


def _special_task_to_dict(special_task):
    job_dict = None
    if special_task.queue_entry:
        job_dict = special_task.queue_entry.job.get_object_dict()
    return _common_entry_to_dict(special_task, special_task.task, job_dict)


def _queue_entry_to_dict(queue_entry):
    return _common_entry_to_dict(queue_entry, 'Job',
                                 queue_entry.job.get_object_dict())


def _compute_next_job_for_tasks(queue_entries, special_tasks):
    """
    For each task, try to figure out the next job that ran after that task.
    This is done using two pieces of information:
    * if the task has a queue entry, we can use that entry's job ID.
    * if the task has a time_started, we can try to compare that against the
      started_on field of queue_entries. this isn't guaranteed to work perfectly
      since queue_entries may also have null started_on values.
    * if the task has neither, or if use of time_started fails, just use the
      last computed job ID.
    """
    next_job_id = None # most recently computed next job
    hqe_index = 0 # index for scanning by started_on times
    for task in special_tasks:
        if task.queue_entry:
            next_job_id = task.queue_entry.job.id
        elif task.time_started is not None:
            for queue_entry in queue_entries[hqe_index:]:
                if queue_entry.started_on is None:
                    continue
                if queue_entry.started_on < task.time_started:
                    break
                next_job_id = queue_entry.job.id

        task.next_job_id = next_job_id

        # advance hqe_index to just after next_job_id
        if next_job_id is not None:
            for queue_entry in queue_entries[hqe_index:]:
                if queue_entry.job.id < next_job_id:
                    break
                hqe_index += 1


def interleave_entries(queue_entries, special_tasks):
    """
    Both lists should be ordered by descending ID.
    """
    _compute_next_job_for_tasks(queue_entries, special_tasks)

    # start with all special tasks that've run since the last job
    interleaved_entries = []
    for task in special_tasks:
        if task.next_job_id is not None:
            break
        interleaved_entries.append(_special_task_to_dict(task))

    # now interleave queue entries with the remaining special tasks
    special_task_index = len(interleaved_entries)
    for queue_entry in queue_entries:
        interleaved_entries.append(_queue_entry_to_dict(queue_entry))
        # add all tasks that ran between this job and the previous one
        for task in special_tasks[special_task_index:]:
            if task.next_job_id < queue_entry.job.id:
                break
            interleaved_entries.append(_special_task_to_dict(task))
            special_task_index += 1

    return interleaved_entries
