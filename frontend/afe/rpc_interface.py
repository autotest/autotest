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

See doctests/rpc_test.txt for (lots) more examples.
"""

__author__ = 'showard@google.com (Steve Howard)'

from frontend import thread_local
from frontend.afe import models, model_logic, control_file, rpc_utils
from autotest_lib.client.common_lib import global_config


# labels

def add_label(name, kernel_config=None, platform=None, only_if_needed=None):
    return models.Label.add_object(name=name, kernel_config=kernel_config,
                                   platform=platform,
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
    return rpc_utils.prepare_for_serialization(
        models.Label.list_objects(filter_data))


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

def generate_control_file(tests, kernel=None, label=None, profilers=[]):
    """\
    Generates a client-side control file to load a kernel and run a set of
    tests.  Returns a dict with the following keys:
    control_file - the control file text
    is_server - is the control file a server-side control file?
    synch_count - how many machines the job uses per autoserv execution.
                  synch_count == 1 means the job is asynchronous.
    dependencies - a list of the names of labels on which the job depends

    tests: list of tests to run
    kernel: kernel to install in generated control file
    label: name of label to grab kernel config from
    profilers: list of profilers to activate during the job
    """
    if not tests:
        return dict(control_file='', is_server=False, synch_count=1,
                    dependencies=[])

    cf_info, test_objects, profiler_objects, label = (
        rpc_utils.prepare_generate_control_file(tests, kernel, label,
                                                profilers))
    cf_info['control_file'] = control_file.generate_control(
        tests=test_objects, kernel=kernel, platform=label,
        profilers=profiler_objects, is_server=cf_info['is_server'])
    return cf_info


def create_job(name, priority, control_file, control_type, timeout=None,
               synch_count=None, hosts=None, meta_hosts=None,
               run_verify=True, one_time_hosts=None, email_list='',
               dependencies=[], reboot_before=None, reboot_after=None):
    """\
    Create and enqueue a job.

    priority: Low, Medium, High, Urgent
    control_file: contents of control file
    control_type: type of control file, Client or Server
    synch_count: how many machines the job uses per autoserv execution.
                 synch_count == 1 means the job is asynchronous.
    hosts: list of hosts to run job on
    meta_hosts: list where each entry is a label name, and for each entry
                one host will be chosen from that label to run the job
                on.
    timeout: hours until job times out
    email_list: string containing emails to mail when the job is done
    dependencies: list of label names on which this job depends
    """

    if timeout is None:
        timeout=global_config.global_config.get_config_value(
            'AUTOTEST_WEB', 'job_timeout_default')

    owner = thread_local.get_user().login
    # input validation
    if not hosts and not meta_hosts and not one_time_hosts:
        raise model_logic.ValidationError({
            'arguments' : "You must pass at least one of 'hosts', "
                          "'meta_hosts', or 'one_time_hosts'"
            })

    labels_by_name = dict((label.name, label)
                          for label in models.Label.objects.all())

    # convert hostnames & meta hosts to host/label objects
    host_objects = models.Host.smart_get_bulk(hosts or [])
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

    # check that each metahost request has enough hosts under the label
    for label, requested_count in metahost_counts.iteritems():
        available_count = label.host_set.count()
        if requested_count > available_count:
            error = ("You have requested %d %s's, but there are only %d."
                     % (requested_count, label.name, available_count))
            raise model_logic.ValidationError({'meta_hosts' : error})

    rpc_utils.check_job_dependencies(host_objects, dependencies)
    dependency_labels = [labels_by_name[label_name]
                         for label_name in dependencies]

    job = models.Job.create(owner=owner, name=name, priority=priority,
                            control_file=control_file,
                            control_type=control_type,
                            synch_count=synch_count,
                            hosts=host_objects + metahost_objects,
                            timeout=timeout,
                            run_verify=run_verify,
                            email_list=email_list.strip(),
                            dependencies=dependency_labels,
                            reboot_before=reboot_before,
                            reboot_after=reboot_after)
    job.queue(host_objects + metahost_objects)
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
    query = job.hostqueueentry_set.filter(deleted=False)

    hosts = []
    meta_hosts = []

    # For each queue entry, if the entry contains a host, add the entry into the
    # hosts list if either:
    #     It is not a metahost.
    #     It was an assigned metahost, and the user wants to keep the specific
    #         assignments.
    # Otherwise, add the metahost to the metahosts list.
    for queue_entry in query:
        if (queue_entry.host and (preserve_metahosts
                                  or not queue_entry.meta_host)):
            hosts.append(queue_entry.host)
        else:
            meta_hosts.append(queue_entry.meta_host.name)

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

    return rpc_utils.prepare_for_serialization(info)


# host queue entries

def get_host_queue_entries(**filter_data):
    """\
    TODO
    """
    query = models.HostQueueEntry.query_objects(filter_data)
    all_dicts = []
    for queue_entry in query.select_related():
        entry_dict = queue_entry.get_object_dict()
        if entry_dict['host'] is not None:
            entry_dict['host'] = queue_entry.host.get_object_dict()
        entry_dict['job'] = queue_entry.job.get_object_dict()
        all_dicts.append(entry_dict)
    return rpc_utils.prepare_for_serialization(all_dicts)


def get_num_host_queue_entries(**filter_data):
    """\
    Get the number of host queue entries associated with this job.
    """
    return models.HostQueueEntry.query_count(filter_data)


def get_hqe_percentage_complete(**filter_data):
    """
    Computes the percentage of host queue entries matching the given filter data
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
    priorities: list of job priority choices
    default_priority: default priority value for new jobs
    users: sorted list of all users
    labels: sorted list of all labels
    tests: sorted list of all tests
    profilers: sorted list of all profilers
    user_login: logged-in username
    host_statuses: sorted list of possible Host statuses
    job_statuses: sorted list of possible HostQueueEntry statuses
    """

    job_fields = models.Job.get_field_dict()

    result = {}
    result['priorities'] = models.Job.Priority.choices()
    default_priority = job_fields['priority'].default
    default_string = models.Job.Priority.get_string(default_priority)
    result['default_priority'] = default_string
    result['users'] = get_users(sort_by=['login'])
    result['labels'] = get_labels(sort_by=['-platform', 'name'])
    result['tests'] = get_tests(sort_by=['name'])
    result['profilers'] = get_profilers(sort_by=['name'])
    result['current_user'] = rpc_utils.prepare_for_serialization(
        thread_local.get_user().get_object_dict())
    result['host_statuses'] = sorted(models.Host.Status.names)
    result['job_statuses'] = sorted(models.HostQueueEntry.Status.names)
    result['job_timeout_default'] = models.Job.DEFAULT_TIMEOUT
    result['reboot_before_options'] = models.RebootBefore.names
    result['reboot_after_options'] = models.RebootAfter.names

    result['status_dictionary'] = {"Abort": "Abort",
                                   "Aborted": "Aborted",
                                   "Verifying": "Verifying Host",
                                   "Pending": "Waiting on other hosts",
                                   "Running": "Running autoserv",
                                   "Completed": "Autoserv completed",
                                   "Failed": "Failed to complete",
                                   "Aborting": "Abort in progress",
                                   "Queued": "Queued",
                                   "Starting": "Next in host's queue",
                                   "Stopped": "Other host(s) failed verify",
                                   "Parsing": "Awaiting parse of final results"}
    return result
