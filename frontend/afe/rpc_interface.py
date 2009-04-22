"""\
Functions to expose over the RPC interface.

For all modify* and delete* functions that ask for an 'id' parameter to
identify the object to operate on, the id may be either
 * the database row ID
 * the name of the object (label name, hostname, user login, etc.)
 * a dictionary containing uniquely identifying field (this option should seldom
   be used)

When specifying foreign key fields (i.e. adding hosts to a label, or adding
users to an ACL group), the given value may be either the database row ID or the
name of the object.

All get* functions return lists of dictionaries.  Each dictionary represents one
object and maps field names to values.

Some examples:
modify_host(2, hostname='myhost') # modify hostname of host with database ID 2
modify_host('ipaj2', hostname='myhost') # modify hostname of host 'ipaj2'
modify_test('sleeptest', test_type='Client', params=', seconds=60')
delete_acl_group(1) # delete by ID
delete_acl_group('Everyone') # delete by name
acl_group_add_users('Everyone', ['mbligh', 'showard'])
get_jobs(owner='showard', status='Queued')

See doctests/001_rpc_test.txt for (lots) more examples.
"""

__author__ = 'showard@google.com (Steve Howard)'

from frontend import thread_local
from frontend.afe import models, model_logic, control_file, rpc_utils
from autotest_lib.client.common_lib import global_config


# labels

def add_label(name, kernel_config=None, platform=None, only_if_needed=None):
    return models.Label.add_object(
            name=name, kernel_config=kernel_config, platform=platform,
            only_if_needed=only_if_needed).id


def modify_label(id, **data):
    models.Label.smart_get(id).update_object(data)


def delete_label(id):
    models.Label.smart_get(id).delete()


def label_add_hosts(id, hosts):
    host_objs = models.Host.smart_get_bulk(hosts)
    models.Label.smart_get(id).host_set.add(*host_objs)


def label_remove_hosts(id, hosts):
    host_objs = models.Host.smart_get_bulk(hosts)
    models.Label.smart_get(id).host_set.remove(*host_objs)


def get_labels(**filter_data):
    """\
    @returns A sequence of nested dictionaries of label information.
    """
    return rpc_utils.prepare_rows_as_nested_dicts(
            models.Label.query_objects(filter_data),
            ('atomic_group',))


# atomic groups

def add_atomic_group(name, max_number_of_machines, description=None):
    return models.AtomicGroup.add_object(
            name=name, max_number_of_machines=max_number_of_machines,
            description=description).id


def modify_atomic_group(id, **data):
    models.AtomicGroup.smart_get(id).update_object(data)


def delete_atomic_group(id):
    models.AtomicGroup.smart_get(id).delete()


def atomic_group_add_labels(id, labels):
    label_objs = models.Label.smart_get_bulk(labels)
    models.AtomicGroup.smart_get(id).label_set.add(*label_objs)


def atomic_group_remove_labels(id, labels):
    label_objs = models.Label.smart_get_bulk(labels)
    models.AtomicGroup.smart_get(id).label_set.remove(*label_objs)


def get_atomic_groups(**filter_data):
    return rpc_utils.prepare_for_serialization(
            models.AtomicGroup.list_objects(filter_data))


# hosts

def add_host(hostname, status=None, locked=None, protection=None):
    return models.Host.add_object(hostname=hostname, status=status,
                                  locked=locked, protection=protection).id


def modify_host(id, **data):
    models.Host.smart_get(id).update_object(data)


def host_add_labels(id, labels):
    labels = models.Label.smart_get_bulk(labels)
    models.Host.smart_get(id).labels.add(*labels)


def host_remove_labels(id, labels):
    labels = models.Label.smart_get_bulk(labels)
    models.Host.smart_get(id).labels.remove(*labels)


def delete_host(id):
    models.Host.smart_get(id).delete()


def get_hosts(multiple_labels=[], exclude_only_if_needed_labels=False,
              **filter_data):
    """\
    multiple_labels: match hosts in all of the labels given.  Should be a
    list of label names.
    exclude_only_if_needed_labels: exclude hosts with at least one
    "only_if_needed" label applied.
    """
    hosts = rpc_utils.get_host_query(multiple_labels,
                                     exclude_only_if_needed_labels,
                                     filter_data)
    host_dicts = []
    for host_obj in hosts:
        host_dict = host_obj.get_object_dict()
        host_dict['labels'] = [label.name for label in host_obj.labels.all()]
        platform = host_obj.platform()
        host_dict['platform'] = platform and platform.name or None
        host_dicts.append(host_dict)
    return rpc_utils.prepare_for_serialization(host_dicts)


def get_num_hosts(multiple_labels=[], exclude_only_if_needed_labels=False,
                  **filter_data):
    hosts = rpc_utils.get_host_query(multiple_labels,
                                     exclude_only_if_needed_labels,
                                     filter_data)
    return hosts.count()


# tests

def add_test(name, test_type, path, author=None, dependencies=None,
             experimental=True, run_verify=None, test_class=None,
             test_time=None, test_category=None, description=None,
             sync_count=1):
    return models.Test.add_object(name=name, test_type=test_type, path=path,
                                  author=author, dependencies=dependencies,
                                  experimental=experimental,
                                  run_verify=run_verify, test_time=test_time,
                                  test_category=test_category,
                                  sync_count=sync_count,
                                  test_class=test_class,
                                  description=description).id


def modify_test(id, **data):
    models.Test.smart_get(id).update_object(data)


def delete_test(id):
    models.Test.smart_get(id).delete()


def get_tests(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Test.list_objects(filter_data))


# profilers

def add_profiler(name, description=None):
    return models.Profiler.add_object(name=name, description=description).id


def modify_profiler(id, **data):
    models.Profiler.smart_get(id).update_object(data)


def delete_profiler(id):
    models.Profiler.smart_get(id).delete()


def get_profilers(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.Profiler.list_objects(filter_data))


# users

def add_user(login, access_level=None):
    return models.User.add_object(login=login, access_level=access_level).id


def modify_user(id, **data):
    models.User.smart_get(id).update_object(data)


def delete_user(id):
    models.User.smart_get(id).delete()


def get_users(**filter_data):
    return rpc_utils.prepare_for_serialization(
        models.User.list_objects(filter_data))


# acl groups

def add_acl_group(name, description=None):
    group = models.AclGroup.add_object(name=name, description=description)
    group.users.add(thread_local.get_user())
    return group.id


def modify_acl_group(id, **data):
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    group.update_object(data)
    group.add_current_user_if_empty()


def acl_group_add_users(id, users):
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    users = models.User.smart_get_bulk(users)
    group.users.add(*users)


def acl_group_remove_users(id, users):
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    users = models.User.smart_get_bulk(users)
    group.users.remove(*users)
    group.add_current_user_if_empty()


def acl_group_add_hosts(id, hosts):
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    hosts = models.Host.smart_get_bulk(hosts)
    group.hosts.add(*hosts)
    group.on_host_membership_change()


def acl_group_remove_hosts(id, hosts):
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    hosts = models.Host.smart_get_bulk(hosts)
    group.hosts.remove(*hosts)
    group.on_host_membership_change()


def delete_acl_group(id):
    models.AclGroup.smart_get(id).delete()


def get_acl_groups(**filter_data):
    acl_groups = models.AclGroup.list_objects(filter_data)
    for acl_group in acl_groups:
        acl_group_obj = models.AclGroup.objects.get(id=acl_group['id'])
        acl_group['users'] = [user.login
                              for user in acl_group_obj.users.all()]
        acl_group['hosts'] = [host.hostname
                              for host in acl_group_obj.hosts.all()]
    return rpc_utils.prepare_for_serialization(acl_groups)


# jobs

def generate_control_file(tests=(), kernel=None, label=None, profilers=(),
                          client_control_file='', use_container=False):
    """
    Generates a client-side control file to load a kernel and run tests.

    @param tests List of tests to run.
    @param kernel Kernel to install in generated control file.
    @param label Name of label to grab kernel config from.
    @param profilers List of profilers to activate during the job.
    @param client_control_file The contents of a client-side control file to
        run at the end of all tests.  If this is supplied, all tests must be
        client side.
        TODO: in the future we should support server control files directly
        to wrap with a kernel.  That'll require changing the parameter
        name and adding a boolean to indicate if it is a client or server
        control file.
    @param use_container unused argument today.  TODO: Enable containers
        on the host during a client side test.

    @returns a dict with the following keys:
        control_file: str, The control file text.
        is_server: bool, is the control file a server-side control file?
        synch_count: How many machines the job uses per autoserv execution.
            synch_count == 1 means the job is asynchronous.
        dependencies: A list of the names of labels on which the job depends.
    """
    if not tests and not control_file:
        return dict(control_file='', is_server=False, synch_count=1,
                    dependencies=[])

    cf_info, test_objects, profiler_objects, label = (
        rpc_utils.prepare_generate_control_file(tests, kernel, label,
                                                profilers))
    cf_info['control_file'] = control_file.generate_control(
        tests=test_objects, kernel=kernel, platform=label,
        profilers=profiler_objects, is_server=cf_info['is_server'],
        client_control_file=client_control_file)
    return cf_info


def create_job(name, priority, control_file, control_type, timeout=None,
               synch_count=None, hosts=(), meta_hosts=(),
               run_verify=True, one_time_hosts=(), email_list='',
               dependencies=(), reboot_before=None, reboot_after=None,
               atomic_group_name=None):
    """\
    Create and enqueue a job.

    priority: Low, Medium, High, Urgent
    control_file: String contents of the control file.
    control_type: Type of control file, Client or Server.
    timeout: Hours after this call returns until the job times out.
    synch_count: How many machines the job uses per autoserv execution.
                 synch_count == 1 means the job is asynchronous.  If an
                 atomic group is given this value is treated as a minimum.
    hosts: List of hosts to run job on.
    meta_hosts: List where each entry is a label name, and for each entry
                one host will be chosen from that label to run the job
                on.
    run_verify: Should the host be verified before running the test?
    one_time_hosts: List of hosts not in the database to run the job on.
    email_list: String containing emails to mail when the job is done
    dependencies: List of label names on which this job depends
    reboot_before: Never, If dirty, or Always
    reboot_after: Never, If all tests passed, or Always
    atomic_group_name: The name of an atomic group to schedule the job on.

    @returns The created Job id number.
    """

    if timeout is None:
        timeout=global_config.global_config.get_config_value(
            'AUTOTEST_WEB', 'job_timeout_default')

    owner = thread_local.get_user().login
    # input validation
    if not (hosts or meta_hosts or one_time_hosts or atomic_group_name):
        raise model_logic.ValidationError({
            'arguments' : "You must pass at least one of 'hosts', "
                          "'meta_hosts', 'one_time_hosts', "
                          "or 'atomic_group_name'"
            })

    # Create and sanity check an AtomicGroup object if requested.
    if atomic_group_name:
        if one_time_hosts:
            raise model_logic.ValidationError(
                    {'one_time_hosts':
                     'One time hosts cannot be used with an Atomic Group.'})
        atomic_group = models.AtomicGroup.smart_get(atomic_group_name)
        if synch_count and synch_count > atomic_group.max_number_of_machines:
            raise model_logic.ValidationError(
                    {'atomic_group_name' :
                     'You have requested a synch_count (%d) greater than the '
                     'maximum machines in the requested Atomic Group (%d).' %
                     (synch_count, atomic_group.max_number_of_machines)})
    else:
        atomic_group = None

    labels_by_name = dict((label.name, label)
                          for label in models.Label.objects.all())

    # convert hostnames & meta hosts to host/label objects
    host_objects = models.Host.smart_get_bulk(hosts)
    metahost_objects = []
    metahost_counts = {}
    for label in meta_hosts or []:
        if label not in labels_by_name:
            raise model_logic.ValidationError(
                {'meta_hosts' : 'Label "%s" not found' % label})
        this_label = labels_by_name[label]
        metahost_objects.append(this_label)
        metahost_counts.setdefault(this_label, 0)
        metahost_counts[this_label] += 1
    for host in one_time_hosts or []:
        this_host = models.Host.create_one_time_host(host)
        host_objects.append(this_host)

    all_host_objects = host_objects + metahost_objects

    # check that each metahost request has enough hosts under the label
    for label, requested_count in metahost_counts.iteritems():
        available_count = label.host_set.count()
        if requested_count > available_count:
            error = ("You have requested %d %s's, but there are only %d."
                     % (requested_count, label.name, available_count))
            raise model_logic.ValidationError({'meta_hosts' : error})

    if atomic_group:
        rpc_utils.check_atomic_group_create_job(
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


    rpc_utils.check_job_dependencies(host_objects, dependencies)
    dependency_labels = [labels_by_name[label_name]
                         for label_name in dependencies]

    for label in metahost_objects + dependency_labels:
        if label.atomic_group and not atomic_group:
            raise model_logic.ValidationError(
                    {'atomic_group_name':
                     'Some meta_hosts or dependencies require an atomic group '
                     'but no atomic_group_name was specified for this job.'})
        elif (label.atomic_group and
              label.atomic_group.name != atomic_group_name):
            raise model_logic.ValidationError(
                    {'atomic_group_name':
                     'Some meta_hosts or dependencies require an atomic group '
                     'other than the one requested for this job.'})

    job = models.Job.create(owner=owner, name=name, priority=priority,
                            control_file=control_file,
                            control_type=control_type,
                            synch_count=synch_count,
                            hosts=all_host_objects,
                            timeout=timeout,
                            run_verify=run_verify,
                            email_list=email_list.strip(),
                            dependencies=dependency_labels,
                            reboot_before=reboot_before,
                            reboot_after=reboot_after)
    job.queue(all_host_objects, atomic_group=atomic_group)
    return job.id


def abort_host_queue_entries(**filter_data):
    """\
    Abort a set of host queue entries.
    """
    query = models.HostQueueEntry.query_objects(filter_data)
    query = query.filter(complete=False)
    models.AclGroup.check_abort_permissions(query)
    host_queue_entries = list(query.select_related())
    rpc_utils.check_abort_synchronous_jobs(host_queue_entries)

    user = thread_local.get_user()
    for queue_entry in host_queue_entries:
        queue_entry.abort(user)


def get_jobs(not_yet_run=False, running=False, finished=False, **filter_data):
    """\
    Extra filter args for get_jobs:
    -not_yet_run: Include only jobs that have not yet started running.
    -running: Include only jobs that have start running but for which not
    all hosts have completed.
    -finished: Include only jobs for which all hosts have completed (or
    aborted).
    At most one of these three fields should be specified.
    """
    filter_data['extra_args'] = rpc_utils.extra_job_filters(not_yet_run,
                                                            running,
                                                            finished)
    jobs = models.Job.list_objects(filter_data)
    models.Job.objects.populate_dependencies(jobs)
    return rpc_utils.prepare_for_serialization(jobs)


def get_num_jobs(not_yet_run=False, running=False, finished=False,
                 **filter_data):
    """\
    See get_jobs() for documentation of extra filter parameters.
    """
    filter_data['extra_args'] = rpc_utils.extra_job_filters(not_yet_run,
                                                            running,
                                                            finished)
    return models.Job.query_count(filter_data)


def get_jobs_summary(**filter_data):
    """\
    Like get_jobs(), but adds a 'status_counts' field, which is a dictionary
    mapping status strings to the number of hosts currently with that
    status, i.e. {'Queued' : 4, 'Running' : 2}.
    """
    jobs = get_jobs(**filter_data)
    ids = [job['id'] for job in jobs]
    all_status_counts = models.Job.objects.get_status_counts(ids)
    for job in jobs:
        job['status_counts'] = all_status_counts[job['id']]
    return rpc_utils.prepare_for_serialization(jobs)


def get_info_for_clone(id, preserve_metahosts):
    """\
    Retrieves all the information needed to clone a job.
    """
    info = {}
    job = models.Job.objects.get(id=id)
    query = job.hostqueueentry_set.filter()

    hosts = []
    meta_hosts = []
    atomic_group_name = None

    # For each queue entry, if the entry contains a host, add the entry into the
    # hosts list if either:
    #     It is not a metahost.
    #     It was an assigned metahost, and the user wants to keep the specific
    #         assignments.
    # Otherwise, add the metahost to the metahosts list.
    for queue_entry in query:
        if (queue_entry.host and (preserve_metahosts
                                  or not queue_entry.meta_host)):
            if queue_entry.deleted:
                continue
            hosts.append(queue_entry.host)
        else:
            meta_hosts.append(queue_entry.meta_host.name)
        if atomic_group_name is None:
            if queue_entry.atomic_group is not None:
                atomic_group_name = queue_entry.atomic_group.name
        else:
            assert atomic_group_name == queue_entry.atomic_group.name, (
                    'DB inconsistency.  HostQueueEntries with multiple atomic'
                    ' groups on job %s: %s != %s' % (
                        id, atomic_group_name, queue_entry.atomic_group.name))

    host_dicts = []

    for host in hosts:
        # one-time host
        if host.invalid:
            host_dict = {}
            host_dict['hostname'] = host.hostname
            host_dict['id'] = host.id
            host_dict['platform'] = '(one-time host)'
            host_dict['locked_text'] = ''
        else:
            host_dict = get_hosts(id=host.id)[0]
            other_labels = host_dict['labels']
            if host_dict['platform']:
                other_labels.remove(host_dict['platform'])
            host_dict['other_labels'] = ', '.join(other_labels)
        host_dicts.append(host_dict)

    meta_host_counts = {}
    for meta_host in meta_hosts:
        meta_host_counts.setdefault(meta_host, 0)
        meta_host_counts[meta_host] += 1

    info['job'] = job.get_object_dict()
    info['job']['dependencies'] = [label.name for label
                                   in job.dependency_labels.all()]
    info['meta_host_counts'] = meta_host_counts
    info['hosts'] = host_dicts
    info['atomic_group_name'] = atomic_group_name

    return rpc_utils.prepare_for_serialization(info)


# host queue entries

def get_host_queue_entries(**filter_data):
    """\
    @returns A sequence of nested dictionaries of host and job information.
    """
    return rpc_utils.prepare_rows_as_nested_dicts(
            models.HostQueueEntry.query_objects(filter_data),
            ('host', 'atomic_group', 'job'))


def get_num_host_queue_entries(**filter_data):
    """\
    Get the number of host queue entries associated with this job.
    """
    return models.HostQueueEntry.query_count(filter_data)


def get_hqe_percentage_complete(**filter_data):
    """
    Computes the fraction of host queue entries matching the given filter data
    that are complete.
    """
    query = models.HostQueueEntry.query_objects(filter_data)
    complete_count = query.filter(complete=True).count()
    total_count = query.count()
    if total_count == 0:
        return 1
    return float(complete_count) / total_count


# other

def echo(data=""):
    """\
    Returns a passed in string. For doing a basic test to see if RPC calls
    can successfully be made.
    """
    return data


def get_static_data():
    """\
    Returns a dictionary containing a bunch of data that shouldn't change
    often and is otherwise inaccessible.  This includes:

    priorities: List of job priority choices.
    default_priority: Default priority value for new jobs.
    users: Sorted list of all users.
    labels: Sorted list of all labels.
    atomic_groups: Sorted list of all atomic groups.
    tests: Sorted list of all tests.
    profilers: Sorted list of all profilers.
    current_user: Logged-in username.
    host_statuses: Sorted list of possible Host statuses.
    job_statuses: Sorted list of possible HostQueueEntry statuses.
    job_timeout_default: The default job timeout length in hours.
    reboot_before_options: A list of valid RebootBefore string enums.
    reboot_after_options: A list of valid RebootAfter string enums.
    motd: Server's message of the day.
    status_dictionary: A mapping from one word job status names to a more
            informative description.
    """

    job_fields = models.Job.get_field_dict()

    result = {}
    result['priorities'] = models.Job.Priority.choices()
    default_priority = job_fields['priority'].default
    default_string = models.Job.Priority.get_string(default_priority)
    result['default_priority'] = default_string
    result['users'] = get_users(sort_by=['login'])
    result['labels'] = get_labels(sort_by=['-platform', 'name'])
    result['atomic_groups'] = get_atomic_groups(sort_by=['name'])
    result['tests'] = get_tests(sort_by=['name'])
    result['profilers'] = get_profilers(sort_by=['name'])
    result['current_user'] = rpc_utils.prepare_for_serialization(
        thread_local.get_user().get_object_dict())
    result['host_statuses'] = sorted(models.Host.Status.names)
    result['job_statuses'] = sorted(models.HostQueueEntry.Status.names)
    result['job_timeout_default'] = models.Job.DEFAULT_TIMEOUT
    result['reboot_before_options'] = models.RebootBefore.names
    result['reboot_after_options'] = models.RebootAfter.names
    result['motd'] = rpc_utils.get_motd()

    result['status_dictionary'] = {"Aborted": "Aborted",
                                   "Verifying": "Verifying Host",
                                   "Pending": "Waiting on other hosts",
                                   "Running": "Running autoserv",
                                   "Completed": "Autoserv completed",
                                   "Failed": "Failed to complete",
                                   "Queued": "Queued",
                                   "Starting": "Next in host's queue",
                                   "Stopped": "Other host(s) failed verify",
                                   "Parsing": "Awaiting parse of final results",
                                   "Gathering": "Gathering log files"}
    return result
