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

import datetime
import common
from autotest_lib.frontend import thread_local
from autotest_lib.frontend.afe import models, model_logic
from autotest_lib.frontend.afe import control_file, rpc_utils
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
    label = models.Label.smart_get(id)
    if label.platform:
        models.Host.check_no_platform(host_objs)
    label.host_set.add(*host_objs)


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

def add_atomic_group(name, max_number_of_machines=None, description=None):
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
    rpc_utils.check_modify_host(data)
    host = models.Host.smart_get(id)
    rpc_utils.check_modify_host_locking(host, data)
    host.update_object(data)


def modify_hosts(host_filter_data, update_data):
    """
    @param host_filter_data: Filters out which hosts to modify.
    @param update_data: A dictionary with the changes to make to the hosts.
    """
    rpc_utils.check_modify_host(update_data)
    hosts = models.Host.query_objects(host_filter_data)
    for host in hosts:
        host.update_object(update_data)


def host_add_labels(id, labels):
    labels = models.Label.smart_get_bulk(labels)
    host = models.Host.smart_get(id)

    platforms = [label.name for label in labels if label.platform]
    if len(platforms) > 1:
        raise model_logic.ValidationError(
            {'labels': 'Adding more than one platform label: %s' %
                       ', '.join(platforms)})
    if len(platforms) == 1:
        models.Host.check_no_platform([host])
    host.labels.add(*labels)


def host_remove_labels(id, labels):
    labels = models.Label.smart_get_bulk(labels)
    models.Host.smart_get(id).labels.remove(*labels)


def set_host_attribute(attribute, value, **host_filter_data):
    """
    @param attribute string name of attribute
    @param value string, or None to delete an attribute
    @param host_filter_data filter data to apply to Hosts to choose hosts to act
    upon
    """
    assert host_filter_data # disallow accidental actions on all hosts
    hosts = models.Host.query_objects(host_filter_data)
    models.AclGroup.check_for_acl_violation_hosts(hosts)

    for host in hosts:
        host.set_or_delete_attribute(attribute, value)


def delete_host(id):
    models.Host.smart_get(id).delete()


def get_hosts(multiple_labels=(), exclude_only_if_needed_labels=False,
              exclude_atomic_group_hosts=False, valid_only=True, **filter_data):
    """
    @param multiple_labels: match hosts in all of the labels given.  Should
            be a list of label names.
    @param exclude_only_if_needed_labels: Exclude hosts with at least one
            "only_if_needed" label applied.
    @param exclude_atomic_group_hosts: Exclude hosts that have one or more
            atomic group labels associated with them.
    """
    hosts = rpc_utils.get_host_query(multiple_labels,
                                     exclude_only_if_needed_labels,
                                     exclude_atomic_group_hosts,
                                     valid_only, filter_data)
    hosts = list(hosts)
    models.Host.objects.populate_relationships(hosts, models.Label,
                                               'label_list')
    models.Host.objects.populate_relationships(hosts, models.AclGroup,
                                               'acl_list')
    models.Host.objects.populate_relationships(hosts, models.HostAttribute,
                                               'attribute_list')
    host_dicts = []
    for host_obj in hosts:
        host_dict = host_obj.get_object_dict()
        host_dict['labels'] = [label.name for label in host_obj.label_list]
        host_dict['platform'], host_dict['atomic_group'] = (rpc_utils.
                find_platform_and_atomic_group(host_obj))
        host_dict['acls'] = [acl.name for acl in host_obj.acl_list]
        host_dict['attributes'] = dict((attribute.attribute, attribute.value)
                                       for attribute in host_obj.attribute_list)
        host_dicts.append(host_dict)
    return rpc_utils.prepare_for_serialization(host_dicts)


def get_num_hosts(multiple_labels=(), exclude_only_if_needed_labels=False,
                  exclude_atomic_group_hosts=False, valid_only=True,
                  **filter_data):
    """
    Same parameters as get_hosts().

    @returns The number of matching hosts.
    """
    hosts = rpc_utils.get_host_query(multiple_labels,
                                     exclude_only_if_needed_labels,
                                     exclude_atomic_group_hosts,
                                     valid_only, filter_data)
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
    @param kernel A list of kernel info dictionaries configuring which kernels
        to boot for this job and other options for them
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
    if not tests and not client_control_file:
        return dict(control_file='', is_server=False, synch_count=1,
                    dependencies=[])

    cf_info, test_objects, profiler_objects, label = (
        rpc_utils.prepare_generate_control_file(tests, kernel, label,
                                                profilers))
    cf_info['control_file'] = control_file.generate_control(
        tests=test_objects, kernels=kernel, platform=label,
        profilers=profiler_objects, is_server=cf_info['is_server'],
        client_control_file=client_control_file)
    return cf_info


def create_job(name, priority, control_file, control_type,
               hosts=(), meta_hosts=(), one_time_hosts=(),
               atomic_group_name=None, synch_count=None, is_template=False,
               timeout=None, max_runtime_hrs=None, run_verify=True,
               email_list='', dependencies=(), reboot_before=None,
               reboot_after=None, parse_failed_repair=None):
    """\
    Create and enqueue a job.

    @param name name of this job
    @param priority Low, Medium, High, Urgent
    @param control_file String contents of the control file.
    @param control_type Type of control file, Client or Server.
    @param synch_count How many machines the job uses per autoserv execution.
    synch_count == 1 means the job is asynchronous.  If an atomic group is
    given this value is treated as a minimum.
    @param is_template If true then create a template job.
    @param timeout Hours after this call returns until the job times out.
    @param max_runtime_hrs Hours from job starting time until job times out
    @param run_verify Should the host be verified before running the test?
    @param email_list String containing emails to mail when the job is done
    @param dependencies List of label names on which this job depends
    @param reboot_before Never, If dirty, or Always
    @param reboot_after Never, If all tests passed, or Always
    @param parse_failed_repair if true, results of failed repairs launched by
    this job will be parsed as part of the job.

    @param hosts List of hosts to run job on.
    @param meta_hosts List where each entry is a label name, and for each entry
    one host will be chosen from that label to run the job on.
    @param one_time_hosts List of hosts not in the database to run the job on.
    @param atomic_group_name The name of an atomic group to schedule the job on.


    @returns The created Job id number.
    """
    user = thread_local.get_user()
    owner = user.login
    # input validation
    if not (hosts or meta_hosts or one_time_hosts or atomic_group_name):
        raise model_logic.ValidationError({
            'arguments' : "You must pass at least one of 'hosts', "
                          "'meta_hosts', 'one_time_hosts', "
                          "or 'atomic_group_name'"
            })

    labels_by_name = dict((label.name, label)
                          for label in models.Label.objects.all())
    atomic_groups_by_name = dict((ag.name, ag)
                                 for ag in models.AtomicGroup.objects.all())

    # Schedule on an atomic group automagically if one of the labels given
    # is an atomic group label and no explicit atomic_group_name was supplied.
    if not atomic_group_name:
        for label_name in meta_hosts or []:
            label = labels_by_name.get(label_name)
            if label and label.atomic_group:
                atomic_group_name = label.atomic_group.name
                break

    # convert hostnames & meta hosts to host/label objects
    host_objects = models.Host.smart_get_bulk(hosts)
    metahost_objects = []
    for label_name in meta_hosts or []:
        if label_name in labels_by_name:
            label = labels_by_name[label_name]
            metahost_objects.append(label)
        elif label_name in atomic_groups_by_name:
            # If given a metahost name that isn't a Label, check to
            # see if the user was specifying an Atomic Group instead.
            atomic_group = atomic_groups_by_name[label_name]
            if atomic_group_name and atomic_group_name != atomic_group.name:
                raise model_logic.ValidationError({
                        'meta_hosts': (
                                'Label "%s" not found.  If assumed to be an '
                                'atomic group it would conflict with the '
                                'supplied atomic group "%s".' % (
                                        label_name, atomic_group_name))})
            atomic_group_name = atomic_group.name
        else:
            raise model_logic.ValidationError(
                {'meta_hosts' : 'Label "%s" not found' % label})

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

    for host in one_time_hosts or []:
        this_host = models.Host.create_one_time_host(host)
        host_objects.append(this_host)

    if reboot_before is None:
        reboot_before = user.get_reboot_before_display()
    if reboot_after is None:
        reboot_after = user.get_reboot_after_display()

    options = dict(name=name,
                   priority=priority,
                   control_file=control_file,
                   control_type=control_type,
                   is_template=is_template,
                   timeout=timeout,
                   max_runtime_hrs=max_runtime_hrs,
                   synch_count=synch_count,
                   run_verify=run_verify,
                   email_list=email_list,
                   dependencies=dependencies,
                   reboot_before=reboot_before,
                   reboot_after=reboot_after,
                   parse_failed_repair=parse_failed_repair)
    return rpc_utils.create_new_job(owner=owner,
                                    options=options,
                                    host_objects=host_objects,
                                    metahost_objects=metahost_objects,
                                    atomic_group=atomic_group)


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


def reverify_hosts(**filter_data):
    """\
    Schedules a set of hosts for verify.
    """
    hosts = models.Host.query_objects(filter_data)
    models.AclGroup.check_for_acl_violation_hosts(hosts)
    models.SpecialTask.schedule_special_task(hosts,
                                             models.SpecialTask.Task.VERIFY)


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
    job_dicts = []
    jobs = list(models.Job.query_objects(filter_data))
    models.Job.objects.populate_relationships(jobs, models.Label,
                                              'dependencies')
    for job in jobs:
        job_dict = job.get_object_dict()
        job_dict['dependencies'] = ','.join(label.name
                                            for label in job.dependencies)
        job_dicts.append(job_dict)
    return rpc_utils.prepare_for_serialization(job_dicts)


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


def get_info_for_clone(id, preserve_metahosts, queue_entry_filter_data=None):
    """\
    Retrieves all the information needed to clone a job.
    """
    job = models.Job.objects.get(id=id)
    job_info = rpc_utils.get_job_info(job,
                                      preserve_metahosts,
                                      queue_entry_filter_data)

    host_dicts = []
    for host in job_info['hosts']:
        host_dict = get_hosts(id=host.id)[0]
        other_labels = host_dict['labels']
        if host_dict['platform']:
            other_labels.remove(host_dict['platform'])
        host_dict['other_labels'] = ', '.join(other_labels)
        host_dicts.append(host_dict)

    for host in job_info['one_time_hosts']:
        host_dict = dict(hostname=host.hostname,
                         id=host.id,
                         platform='(one-time host)',
                         locked_text='')
        host_dicts.append(host_dict)

    # convert keys from Label objects to strings (names of labels)
    meta_host_counts = dict((meta_host.name, count) for meta_host, count
                            in job_info['meta_host_counts'].iteritems())

    info = dict(job=job.get_object_dict(),
                meta_host_counts=meta_host_counts,
                hosts=host_dicts)
    info['job']['dependencies'] = job_info['dependencies']
    if job_info['atomic_group']:
        info['atomic_group_name'] = (job_info['atomic_group']).name
    else:
        info['atomic_group_name'] = None

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


# special tasks

def get_special_tasks(**filter_data):
    return rpc_utils.prepare_rows_as_nested_dicts(
            models.SpecialTask.query_objects(filter_data),
            ('host', 'queue_entry'))


# support for host detail view

def get_host_queue_entries_and_special_tasks(hostname, query_start=None,
                                             query_limit=None):
    """
    @returns an interleaved list of HostQueueEntries and SpecialTasks,
            in approximate run order.  each dict contains keys for type, host,
            job, status, started_on, execution_path, and ID.
    """
    total_limit = None
    if query_limit is not None:
        total_limit = query_start + query_limit
    filter_data = {'host__hostname': hostname,
                   'query_limit': total_limit,
                   'sort_by': ['-id']}

    queue_entries = list(models.HostQueueEntry.query_objects(filter_data))
    special_tasks = list(models.SpecialTask.query_objects(filter_data))

    interleaved_entries = rpc_utils.interleave_entries(queue_entries,
                                                       special_tasks)
    if query_start is not None:
        interleaved_entries = interleaved_entries[query_start:]
    if query_limit is not None:
        interleaved_entries = interleaved_entries[:query_limit]
    return rpc_utils.prepare_for_serialization(interleaved_entries)


def get_num_host_queue_entries_and_special_tasks(hostname):
    filter_data = {'host__hostname': hostname}
    return (models.HostQueueEntry.query_count(filter_data)
            + models.SpecialTask.query_count(filter_data))


# recurring run

def get_recurring(**filter_data):
    return rpc_utils.prepare_rows_as_nested_dicts(
            models.RecurringRun.query_objects(filter_data),
            ('job', 'owner'))


def get_num_recurring(**filter_data):
    return models.RecurringRun.query_count(filter_data)


def delete_recurring_runs(**filter_data):
    to_delete = models.RecurringRun.query_objects(filter_data)
    to_delete.delete()


def create_recurring_run(job_id, start_date, loop_period, loop_count):
    owner = thread_local.get_user().login
    job = models.Job.objects.get(id=job_id)
    return job.create_recurring_job(start_date=start_date,
                                    loop_period=loop_period,
                                    loop_count=loop_count,
                                    owner=owner)


# other

def echo(data=""):
    """\
    Returns a passed in string. For doing a basic test to see if RPC calls
    can successfully be made.
    """
    return data


def get_motd():
    """\
    Returns the message of the day as a string.
    """
    return rpc_utils.get_motd()


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
    parse_failed_repair_default: Default value for the parse_failed_repair job
    option.
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
    result['job_max_runtime_hrs_default'] = models.Job.DEFAULT_MAX_RUNTIME_HRS
    result['parse_failed_repair_default'] = bool(
        models.Job.DEFAULT_PARSE_FAILED_REPAIR)
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
                                   "Gathering": "Gathering log files",
                                   "Template": "Template job for recurring run",
                                   "Waiting": "Waiting for scheduler action"}
    return result


def get_server_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
