"""
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
import logging
import os
import xmlrpclib
# psutil is a non stdlib import, it needs to be installed
import psutil
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend.afe import models, model_logic, model_attributes
from autotest.frontend.afe import control_file, rpc_utils, reservations
from autotest.server.hosts.remote import get_install_server_info
from autotest.client.shared import version
from autotest.client.shared.settings import settings


#
# IMPORTANT: please update INTERFACE_VERSION with the current date whenever
# the interface changes, so that RPC clients can handle the changes
#
INTERFACE_VERSION = (2013, 9, 11)


# labels

def add_label(name, kernel_config=None, platform=None, only_if_needed=None):
    """
    Add (create) label.

    :param name: The name of the label.
    :param kernel_config: Kernel configuration (optional).
    :param platform: Platform (optional).
    :param only_if_need: Only if needed (optional).
    :return: ID.
    """
    return models.Label.add_object(
        name=name, kernel_config=kernel_config, platform=platform,
        only_if_needed=only_if_needed).id


def modify_label(id, **data):
    """
    Modify (update) label.

    :param id: Label identification.
    :param data: Fields to modify.
    :return: None.
    """
    models.Label.smart_get(id).update_object(data)


def delete_label(id):
    """
    Delete label.

    :param id: Label identification.
    :return: None.
    """
    models.Label.smart_get(id).delete()


def label_add_hosts(id, hosts):
    """
    Add multiple hosts to a label.

    :param id: Label identification.
    :param hosts: A sequence of hosts.
    :return: None.
    """
    host_objs = models.Host.smart_get_bulk(hosts)
    label = models.Label.smart_get(id)
    if label.platform:
        models.Host.check_no_platform(host_objs)
    label.host_set.add(*host_objs)


def label_remove_hosts(id, hosts):
    """
    Remove hosts from label.

    :param id: Label identification.
    :param hosts: A sequence of hosts.
    :return: None.
    """
    host_objs = models.Host.smart_get_bulk(hosts)
    models.Label.smart_get(id).host_set.remove(*host_objs)


def get_labels(**filter_data):
    """
    Get labels.

    :param filter_data: Filters out which labels to get.
    :return: A sequence of nested dictionaries of label information.
    """
    return rpc_utils.prepare_rows_as_nested_dicts(
        models.Label.query_objects(filter_data),
        ('atomic_group',))


# atomic groups

def add_atomic_group(name, max_number_of_machines=None, description=None):
    """
    Add (create) atomic group.

    :param name: Name of the atomic group.
    :param max_number_of_machines: Maximum number of machines (optional).
    :param description: Description (optional).
    :return: ID.
    """
    return models.AtomicGroup.add_object(
        name=name, max_number_of_machines=max_number_of_machines,
        description=description).id


def modify_atomic_group(id, **data):
    """
    Modify (update) atomic group.

    :param data: Fields to modify.
    :return: None.
    """
    models.AtomicGroup.smart_get(id).update_object(data)


def delete_atomic_group(id):
    """
    Delete atomic group.

    :param id: Atomic group identification.
    :return: None.
    """
    models.AtomicGroup.smart_get(id).delete()


def atomic_group_add_labels(id, labels):
    """
    Add labels to atomic group.

    :param id: Atomic group identification.
    :param labels: Sequence of labels.
    :return: None.
    """
    label_objs = models.Label.smart_get_bulk(labels)
    models.AtomicGroup.smart_get(id).label_set.add(*label_objs)


def atomic_group_remove_labels(id, labels):
    """
    Remove labels from atomic group.

    :param id: Atomic group identification.
    :param labels: Sequence of labels.
    :return: None.
    """
    label_objs = models.Label.smart_get_bulk(labels)
    models.AtomicGroup.smart_get(id).label_set.remove(*label_objs)


def get_atomic_groups(**filter_data):
    """
    Get atomic groups.

    :param filter_data: Filters out which atomic groups to get.
    :return: Sequence of atomic groups.
    """
    return rpc_utils.prepare_for_serialization(
        models.AtomicGroup.list_objects(filter_data))


# hosts

def add_host(hostname, status=None, locked=None, protection=None):
    """
    Add (create) host.

    :param hostname: The hostname.
    :param status: Status (optional).
    :param locked: Locked (optional).
    :param protection: Protection (optional).
    :return: ID.
    """
    return models.Host.add_object(hostname=hostname, status=status,
                                  locked=locked, protection=protection).id


def modify_host(id, **data):
    """
    Modify (update) host.

    :param id: Host identification.
    :param data: Fields to modify.
    :return: None.
    """
    rpc_utils.check_modify_host(data)
    host = models.Host.smart_get(id)
    rpc_utils.check_modify_host_locking(host, data)
    host.update_object(data)


def modify_hosts(host_filter_data, update_data):
    """
    Modify multiple hosts.

    :param host_filter_data: Filters out which hosts to modify.
    :param update_data: A dictionary with the changes to make to the hosts.
    :return: None.
    """
    rpc_utils.check_modify_host(update_data)
    hosts = models.Host.query_objects(host_filter_data)
    for host in hosts:
        host.update_object(update_data)


def host_add_labels(id, labels):
    """
    Add labels to host.

    :param id: Host identification.
    :param labels: Sequence of labels.
    :return: None.
    """
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
    """
    Remove labels from host.

    :param id: Host Identification.
    :param labels: Sequence of labels.
    :return: None.
    """
    labels = models.Label.smart_get_bulk(labels)
    models.Host.smart_get(id).labels.remove(*labels)


def set_host_attribute(attribute, value, **host_filter_data):
    """
    Set host attribute.

    :param attribute: string name of attribute.
    :param value: string, or None to delete an attribute.
    :param host_filter_data: filter data to apply to Hosts to choose hosts
    to act upon.
    :return: None.
    """
    assert host_filter_data  # disallow accidental actions on all hosts
    hosts = models.Host.query_objects(host_filter_data)
    models.AclGroup.check_for_acl_violation_hosts(hosts)

    for host in hosts:
        host.set_or_delete_attribute(attribute, value)


def delete_host(id):
    """
    Delete host.

    :param id: Host identification.
    :return: None.
    """
    models.Host.smart_get(id).delete()


def get_hosts(multiple_labels=(), exclude_only_if_needed_labels=False,
              exclude_atomic_group_hosts=False, valid_only=True, **filter_data):
    """
    Get hosts.

    :param multiple_labels: match hosts in all of the labels given (optional).
    Should be a list of label names.
    :param exclude_only_if_needed_labels: Exclude hosts with
    at least one "only_if_needed" label applied (optional).
    :param exclude_atomic_group_hosts: Exclude hosts that have one or more
            atomic group labels associated with them.
    :param valid_only: Filter valid hosts (optional).
    :param filter_data: Filters out which hosts to get.
    :return: Sequence of hosts.
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

    install_server = None
    install_server_info = get_install_server_info()
    install_server_type = install_server_info.get('type', None)
    install_server_url = install_server_info.get('xmlrpc_url', None)

    if install_server_type == 'cobbler' and install_server_url:
        install_server = xmlrpclib.ServerProxy(install_server_url)

    host_dicts = []
    for host_obj in hosts:
        host_dict = host_obj.get_object_dict()
        host_dict['labels'] = [label.name for label in host_obj.label_list]
        host_dict['platform'], host_dict['atomic_group'] = (rpc_utils.
                                                            find_platform_and_atomic_group(host_obj))
        host_dict['acls'] = [acl.name for acl in host_obj.acl_list]
        host_dict['attributes'] = dict((attribute.attribute, attribute.value)
                                       for attribute in host_obj.attribute_list)

        error_encountered = True
        if install_server is not None:
            system_params = {"name": host_dict['hostname']}
            system_list = install_server.find_system(system_params, True)

            if len(system_list) < 1:
                msg = 'System "%s" not found on install server'
                rpc_logger = logging.getLogger('rpc_logger')
                rpc_logger.info(msg, host_dict['hostname'])

            elif len(system_list) > 1:
                msg = 'Found multiple systems on install server named %s'

                if install_server_type == 'cobbler':
                    msg = '%s. This should never happen on cobbler' % msg
                rpc_logger = logging.getLogger('rpc_logger')
                rpc_logger.error(msg, host_dict['hostname'])

            else:
                system = system_list[0]

                if host_dict['platform']:
                    error_encountered = False
                    profiles = sorted(install_server.get_item_names('profile'))
                    host_dict['profiles'] = profiles
                    host_dict['profiles'].insert(0, 'Do_not_install')
                    use_current_profile = settings.get_value('INSTALL_SERVER',
                                                             'use_current_profile', type=bool, default=True)
                    if use_current_profile:
                        host_dict['current_profile'] = system['profile']
                    else:
                        host_dict['current_profile'] = 'Do_not_install'

        if error_encountered:
            host_dict['profiles'] = ['N/A']
            host_dict['current_profile'] = 'N/A'

        host_dicts.append(host_dict)

    return rpc_utils.prepare_for_serialization(host_dicts)


def get_num_hosts(multiple_labels=(), exclude_only_if_needed_labels=False,
                  exclude_atomic_group_hosts=False, valid_only=True,
                  **filter_data):
    """
    Get the number of hosts. Same parameters as get_hosts().

    :return: The number of matching hosts.
    """
    hosts = rpc_utils.get_host_query(multiple_labels,
                                     exclude_only_if_needed_labels,
                                     exclude_atomic_group_hosts,
                                     valid_only, filter_data)
    return hosts.count()


def get_install_server_profiles():
    """
    Get install server profiles.

    :return: Sequence of profiles.
    """
    install_server = None
    install_server_info = get_install_server_info()
    install_server_type = install_server_info.get('type', None)
    install_server_url = install_server_info.get('xmlrpc_url', None)

    if install_server_type == 'cobbler' and install_server_url:
        install_server = xmlrpclib.ServerProxy(install_server_url)

    if install_server is None:
        return None

    return install_server.get_item_names('profile')


def get_profiles():
    """
    Get profiles.

    :return: Sequence of profiles.
    """
    error_encountered = True
    profile_dicts = []
    profiles = get_install_server_profiles()
    if profiles is not None:
        if len(profiles) < 1:
            msg = 'No profiles defined on install server'
            rpc_logger = logging.getLogger('rpc_logger')
            rpc_logger.info(msg)

        else:
            error_encountered = False
            # not sorted
            profiles.sort()
            profile_dicts.append(dict(name="Do_not_install"))
            for profile in profiles:
                profile_dicts.append(dict(name=profile))

    if error_encountered:
        profile_dicts.append(dict(name="N/A"))

    return rpc_utils.prepare_for_serialization(profile_dicts)


def get_num_profiles():
    """
    Get the number of profiles. Same parameters as get_profiles().

    :return: The number of defined profiles.
    """
    error_encountered = True
    profiles = get_install_server_profiles()
    if profiles is not None:
        if len(profiles) < 1:
            # 'N/A'
            return 1

        else:
            # include 'Do_not_install'
            return len(profiles) + 1

    if error_encountered:
        # 'N/A'
        return 1


def reserve_hosts(host_filter_data, username=None):
    """
    Reserve some hosts.

    :param host_filter_data: Filters out which hosts to reserve.
    :param username: login of the user reserving hosts
    :type username: str
    :return: None.
    """
    hosts = models.Host.query_objects(host_filter_data)
    reservations.create(hosts_to_reserve=[h.hostname for h in hosts],
                        username=username)


def release_hosts(host_filter_data, username=None):
    """
    Release some hosts.

    :param host_filter_data: Filters out which hosts to release.
    :param username: login of the user reserving hosts
    :type username: str
    :return: None.
    """
    hosts = models.Host.query_objects(host_filter_data)
    reservations.release(hosts_to_release=[h.hostname for h in hosts],
                         username=username)


def force_release_hosts(host_filter_data, username=None):
    """
    Force release some hosts (remove all ACLs).

    :param host_filter_data: Filters out which hosts to release.
    :param username: login of the user releasing hosts, which needs have elevated privileges
    :type username: str
    :return: None.
    """
    hosts = models.Host.query_objects(host_filter_data)
    reservations.force_release(hosts_to_release=[h.hostname for h in hosts],
                               username=username)


# tests

def add_test(name, test_type, path, author=None, dependencies=None,
             experimental=True, run_verify=None, test_class=None,
             test_time=None, test_category=None, description=None,
             sync_count=1):
    """
    Add (create) test.

    :param name: Test name.
    :param test_type: Test type (Client or Server).
    :param path: Relative path to the test.
    :param author: The author of the test (optional).
    :param dependencies: Dependencies (optional).
    :param experimental: Experimental? (True or False) (optional).
    :param run_verify: Run verify? (True or False) (optional).
    :param test_class: Test class (optional).
    :param test_time: Test time (optional).
    :param test_category: Test category (optional).
    :param description: Description (optional).
    :param sync_count: Sync count (optional).
    :return: ID.
    """
    return models.Test.add_object(name=name, test_type=test_type, path=path,
                                  author=author, dependencies=dependencies,
                                  experimental=experimental,
                                  run_verify=run_verify, test_time=test_time,
                                  test_category=test_category,
                                  sync_count=sync_count,
                                  test_class=test_class,
                                  description=description).id


def modify_test(id, **data):
    """
    Modify (update) test.

    :param id: Test identification.
    :param data: Test data to modify.
    :return: None.
    """
    models.Test.smart_get(id).update_object(data)


def delete_test(id):
    """
    Delete test.

    :param id: Test identification.
    :return: None.
    """
    models.Test.smart_get(id).delete()


def get_tests(**filter_data):
    """
    Get tests.

    :param filter_data: Filters out which tests to get.
    :return: Sequence of tests.
    """
    return rpc_utils.prepare_for_serialization(
        models.Test.list_objects(filter_data))


# profilers

def add_profiler(name, description=None):
    """
    Add (create) profiler.

    :param name: The name of the profiler.
    :param description: Description (optional).
    :return: ID.
    """
    return models.Profiler.add_object(name=name, description=description).id


def modify_profiler(id, **data):
    """
    Modify (update) profiler.

    :param id: Profiler identification.
    :param data: Profiler data to modify.
    :return: None.
    """
    models.Profiler.smart_get(id).update_object(data)


def delete_profiler(id):
    """
    Delete profiler.

    :param id: Profiler identification.
    :return: None.
    """
    models.Profiler.smart_get(id).delete()


def get_profilers(**filter_data):
    """
    Get all profilers.

    :param filter_data: Filters out which profilers to get.
    :return: Sequence of profilers.
    """
    return rpc_utils.prepare_for_serialization(
        models.Profiler.list_objects(filter_data))


# users

def add_user(login, access_level=None):
    """
    Add (create) user.

    :param login: The login name.
    :param acess_level: Access level (optional).
    :return: ID.
    """
    return models.User.add_object(login=login, access_level=access_level).id


def modify_user(id, **data):
    """
    Modify (update) user.

    :param id: User identification.
    :param data: User data to modify.
    :return: None.
    """
    models.User.smart_get(id).update_object(data)


def delete_user(id):
    """
    Delete user.

    :param id: User identification.
    :return: None.
    """
    models.User.smart_get(id).delete()


def get_users(**filter_data):
    """
    Get users.

    :param filter_data: Filters out which users to get.
    :return: Sequence of users.
    """
    return rpc_utils.prepare_for_serialization(
        models.User.list_objects(filter_data))


# acl groups

def add_acl_group(name, description=None):
    """
    Add (create) ACL group.

    :param name: The name of the ACL group.
    :param description: Description (optional).
    :return: ID.
    """
    group = models.AclGroup.add_object(name=name, description=description)
    group.users.add(models.User.current_user())
    return group.id


def modify_acl_group(id, **data):
    """
    Modify (update) ACL group.

    :param id: ACL group identification.
    :param data: ACL group data to modify.
    :return: None.
    """
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    group.update_object(data)
    group.add_current_user_if_empty()


def acl_group_add_users(id, users):
    """
    Add users to an ACL group.

    :param id: ACL group identification.
    :param users: Sequence of users.
    :return: None.
    """
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    users = models.User.smart_get_bulk(users)
    group.users.add(*users)


def acl_group_remove_users(id, users):
    """
    Remove users from an ACL group.

    :param id: ACL group identification.
    :param users: Sequence of users.
    :return: None.
    """
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    users = models.User.smart_get_bulk(users)
    group.users.remove(*users)
    group.add_current_user_if_empty()


def acl_group_add_hosts(id, hosts):
    """
    Add hosts to an ACL group.

    :param id: ACL group identification.
    :param hosts: Sequence of hosts to add.
    :return: None.
    """
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    hosts = models.Host.smart_get_bulk(hosts)
    group.hosts.add(*hosts)
    group.on_host_membership_change()


def acl_group_remove_hosts(id, hosts):
    """
    Remove hosts from an ACL group.

    :param id: ACL group identification.
    :param hosts: Sequence of hosts to remove.
    :return: None.
    """
    group = models.AclGroup.smart_get(id)
    group.check_for_acl_violation_acl_group()
    hosts = models.Host.smart_get_bulk(hosts)
    group.hosts.remove(*hosts)
    group.on_host_membership_change()


def delete_acl_group(id):
    """
    Delete ACL group.

    :param id: ACL group identification.
    :return: None.
    """
    models.AclGroup.smart_get(id).delete()


def get_acl_groups(**filter_data):
    """
    Get ACL groups.

    :param filter_data: Filters out which ACL groups to get.
    :return: Sequence of ACL groups.
    """
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
                          client_control_file='', use_container=False,
                          profile_only=None, upload_kernel_config=False):
    """
    Generates a client-side control file to load a kernel and run tests.

    :param tests List of tests to run.
    :param kernel A list of kernel info dictionaries configuring which kernels
        to boot for this job and other options for them
    :param label Name of label to grab kernel config from.
    :param profilers List of profilers to activate during the job.
    :param client_control_file The contents of a client-side control file to
        run at the end of all tests.  If this is supplied, all tests must be
        client side.
        TODO: in the future we should support server control files directly
        to wrap with a kernel.  That'll require changing the parameter
        name and adding a boolean to indicate if it is a client or server
        control file.
    :param use_container unused argument today.  TODO: Enable containers
        on the host during a client side test.
    :param profile_only A boolean that indicates what default profile_only
        mode to use in the control file. Passing None will generate a
        control file that does not explcitly set the default mode at all.
    :param upload_kernel_config: if enabled it will generate server control
            file code that uploads the kernel config file to the client and
            tells the client of the new (local) path when compiling the kernel;
            the tests must be server side tests

    :return: a dict with the following keys:
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
        client_control_file=client_control_file, profile_only=profile_only,
        upload_kernel_config=upload_kernel_config)
    return cf_info


def create_parameterized_job(name, priority, test, parameters, kernel=None,
                             label=None, profiles=[], profilers=(),
                             profiler_parameters=None,
                             use_container=False, profile_only=None,
                             upload_kernel_config=False, hosts=[],
                             meta_hosts=[], meta_host_profiles=[], one_time_hosts=[],
                             atomic_group_name=None, synch_count=None,
                             is_template=False, timeout=None,
                             max_runtime_hrs=None, run_verify=True,
                             email_list='', dependencies=(), reboot_before=None,
                             reboot_after=None, parse_failed_repair=None,
                             hostless=False, keyvals=None, drone_set=None,
                             reserve_hosts=False):
    """
    Creates and enqueues a parameterized job.

    Most parameters a combination of the parameters for generate_control_file()
    and create_job(), with the exception of:

    :param test name or ID of the test to run
    :param parameters a map of parameter name ->
                          tuple of (param value, param type)
    :param profiler_parameters a dictionary of parameters for the profilers:
                                   key: profiler name
                                   value: dict of param name -> tuple of
                                                                (param value,
                                                                 param type)
    """
    # Save the values of the passed arguments here. What we're going to do with
    # them is pass them all to rpc_utils.get_create_job_common_args(), which
    # will extract the subset of these arguments that apply for
    # rpc_utils.create_job_common(), which we then pass in to that function.
    args = locals()

    # Set up the parameterized job configs
    test_obj = models.Test.smart_get(test)
    if test_obj.test_type == model_attributes.TestTypes.SERVER:
        control_type = models.Job.ControlType.SERVER
    else:
        control_type = models.Job.ControlType.CLIENT

    try:
        label = models.Label.smart_get(label)
    except models.Label.DoesNotExist:
        label = None

    kernel_objs = models.Kernel.create_kernels(kernel)
    profiler_objs = [models.Profiler.smart_get(profiler)
                     for profiler in profilers]

    parameterized_job = models.ParameterizedJob.objects.create(
        test=test_obj, label=label, use_container=use_container,
        profile_only=profile_only,
        upload_kernel_config=upload_kernel_config)
    parameterized_job.kernels.add(*kernel_objs)

    for profiler in profiler_objs:
        parameterized_profiler = models.ParameterizedJobProfiler.objects.create(
            parameterized_job=parameterized_job,
            profiler=profiler)
        profiler_params = profiler_parameters.get(profiler.name, {})
        for name, (value, param_type) in profiler_params.iteritems():
            models.ParameterizedJobProfilerParameter.objects.create(
                parameterized_job_profiler=parameterized_profiler,
                parameter_name=name,
                parameter_value=value,
                parameter_type=param_type)

    try:
        for parameter in test_obj.testparameter_set.all():
            if parameter.name in parameters:
                param_value, param_type = parameters.pop(parameter.name)
                parameterized_job.parameterizedjobparameter_set.create(
                    test_parameter=parameter, parameter_value=param_value,
                    parameter_type=param_type)

        if parameters:
            raise Exception('Extra parameters remain: %r' % parameters)

        return rpc_utils.create_job_common(
            parameterized_job=parameterized_job.id,
            control_type=control_type,
            **rpc_utils.get_create_job_common_args(args))
    except:
        parameterized_job.delete()
        raise


def create_job(name, priority, control_file, control_type,
               hosts=[], profiles=[], meta_hosts=[], meta_host_profiles=[],
               one_time_hosts=[], atomic_group_name=None, synch_count=None,
               is_template=False, timeout=None, max_runtime_hrs=None,
               run_verify=True, email_list='', dependencies=(), reboot_before=None,
               reboot_after=None, parse_failed_repair=None, hostless=False,
               keyvals=None, drone_set=None, reserve_hosts=False):
    """
    Create and enqueue a job.

    :param name: name of this job
    :param priority: Low, Medium, High, Urgent
    :param control_file: String contents of the control file.
    :param control_type: Type of control file, Client or Server.
    :param synch_count: How many machines the job uses per autoserv execution.
                        synch_count == 1 means the job is asynchronous. If an
                        atomic group is given this value is treated as a
                        minimum.
    :param is_template: If true then create a template job.
    :param timeout: Hours after this call returns until the job times out.
    :param max_runtime_hrs: Hours from job starting time until job times out
    :param run_verify: Should the host be verified before running the test?
    :param email_list: String containing emails to mail when the job is done
    :param dependencies: List of label names on which this job depends
    :param reboot_before: Never, If dirty, or Always
    :param reboot_after: Never, If all tests passed, or Always
    :param parse_failed_repair: if true, results of failed repairs launched by
                                this job will be parsed as part of the job.
    :param hostless: if true, create a hostless job
    :param keyvals: dict of keyvals to associate with the job
    :param hosts: List of hosts to run job on.
    :param profiles: List of profiles to use, in sync with @hosts list
    :param meta_hosts: List where each entry is a label name, and for each
                       entry one host will be chosen from that label to run
                       the job on.
    :param one_time_hosts: List of hosts not in the database to run the job on.
    :param atomic_group_name: name of an atomic group to schedule the job on.
    :param drone_set: The name of the drone set to run this test on.
    :param reserve_hosts: If set we will reseve the hosts that were allocated
                          for this job
    :returns: The created Job id number.
    :rtype: integer
    """
    return rpc_utils.create_job_common(
        **rpc_utils.get_create_job_common_args(locals()))


def abort_host_queue_entries(**filter_data):
    """
    Abort a set of host queue entries.

    :param filter_data: Filters out which hosts.
    :return: None.
    """
    query = models.HostQueueEntry.query_objects(filter_data)
    query = query.filter(complete=False)
    models.AclGroup.check_abort_permissions(query)
    host_queue_entries = list(query.select_related())
    rpc_utils.check_abort_synchronous_jobs(host_queue_entries)

    for queue_entry in host_queue_entries:
        queue_entry.abort()


def reverify_hosts(**filter_data):
    """
    Schedules a set of hosts for verify.

    :param filter_data: Filters out which hosts.
    :return: A list of hostnames that a verify task was created for.
    """
    hosts = models.Host.query_objects(filter_data)
    models.AclGroup.check_for_acl_violation_hosts(hosts)
    for host in hosts:
        models.SpecialTask.schedule_special_task(host,
                                                 models.SpecialTask.Task.VERIFY)
    return list(sorted(host.hostname for host in hosts))


def get_jobs(not_yet_run=False, running=False, finished=False, **filter_data):
    """
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
    models.Job.objects.populate_relationships(jobs, models.JobKeyval, 'keyvals')
    for job in jobs:
        job_dict = job.get_object_dict()
        job_dict['dependencies'] = ','.join(label.name
                                            for label in job.dependencies)
        job_dict['keyvals'] = dict((keyval.key, keyval.value)
                                   for keyval in job.keyvals)
        job_dicts.append(job_dict)
    return rpc_utils.prepare_for_serialization(job_dicts)


def get_num_jobs(not_yet_run=False, running=False, finished=False,
                 **filter_data):
    """
    See get_jobs() for documentation of extra filter parameters.
    """
    filter_data['extra_args'] = rpc_utils.extra_job_filters(not_yet_run,
                                                            running,
                                                            finished)
    return models.Job.query_count(filter_data)


def get_jobs_summary(**filter_data):
    """
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
    """
    Retrieves all the information needed to clone a job.
    """
    job = models.Job.objects.get(id=id)
    job_info = rpc_utils.get_job_info(job,
                                      preserve_metahosts,
                                      queue_entry_filter_data)

    host_dicts = []
    for host, profile in zip(job_info['hosts'], job_info['profiles']):
        host_dict = get_hosts(id=host.id)[0]
        other_labels = host_dict['labels']
        if host_dict['platform']:
            other_labels.remove(host_dict['platform'])
        host_dict['other_labels'] = ', '.join(other_labels)
        host_dict['profile'] = profile
        host_dicts.append(host_dict)

    for host in job_info['one_time_hosts']:
        host_dict = dict(hostname=host.hostname,
                         id=host.id,
                         platform='(one-time host)',
                         locked_text='')
        host_dicts.append(host_dict)

    meta_host_dicts = []
    # convert keys from Label objects to strings (names of labels)
    meta_host_counts = dict((meta_host.name, count) for meta_host, count
                            in job_info['meta_host_counts'].iteritems())
    for meta_host, meta_host_profile in zip(job_info['meta_hosts'], job_info['meta_host_profiles']):
        meta_host_dict = dict(name=meta_host.name, count=meta_host_counts[meta_host.name], profile=meta_host_profile)
        meta_host_dicts.append(meta_host_dict)

    info = dict(job=job.get_object_dict(),
                meta_hosts=meta_host_dicts,
                hosts=host_dicts)
    info['job']['dependencies'] = job_info['dependencies']
    if job_info['atomic_group']:
        info['atomic_group_name'] = (job_info['atomic_group']).name
    else:
        info['atomic_group_name'] = None
    info['hostless'] = job_info['hostless']
    info['drone_set'] = job.drone_set and job.drone_set.name

    return rpc_utils.prepare_for_serialization(info)


# host queue entries

def get_host_queue_entries(**filter_data):
    """
    :return: A sequence of nested dictionaries of host and job information.
    """
    return rpc_utils.prepare_rows_as_nested_dicts(
        models.HostQueueEntry.query_objects(filter_data),
        ('host', 'atomic_group', 'job'))


def get_num_host_queue_entries(**filter_data):
    """
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
    :return: an interleaved list of HostQueueEntries and SpecialTasks,
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
    return (models.HostQueueEntry.query_count(filter_data) +
            models.SpecialTask.query_count(filter_data))


# recurring run

def get_recurring(**filter_data):
    """
    Return recurring jobs.

    :param filter_data: Filters out which recurring jobs to get.
    :return: Sequence of recurring jobs.
    """
    return rpc_utils.prepare_rows_as_nested_dicts(
        models.RecurringRun.query_objects(filter_data),
        ('job', 'owner'))


def get_num_recurring(**filter_data):
    """
    Get the number of recurring jobs.

    :param filter_data: Filters out which recurring jobs to get.
    :return: Number of recurring jobs.
    """
    return models.RecurringRun.query_count(filter_data)


def delete_recurring_runs(**filter_data):
    """
    Delete recurring jobs.

    :param filter_data: Filters out which recurring jobs to delete.
    :return: None.
    """
    to_delete = models.RecurringRun.query_objects(filter_data)
    to_delete.delete()


def create_recurring_run(job_id, start_date, loop_period, loop_count):
    """
    Create (add) a recurring job.

    :param job_id: Job identification.
    :param start_date: Start date.
    :param loop_period: Loop period.
    :param loop_count: Loo counter.
    :return: None.
    """
    owner = models.User.current_user().login
    job = models.Job.objects.get(id=job_id)
    return job.create_recurring_job(start_date=start_date,
                                    loop_period=loop_period,
                                    loop_count=loop_count,
                                    owner=owner)


# other

def echo(data=""):
    """
    Echo - for doing a basic test to see if RPC calls
    can successfully be made.

    :param data: Object to echo, it must be serializable.
    :return: Object echoed back.
    """
    return data


def get_motd():
    """
    Returns the message of the day (MOTD).

    :return: String with MOTD.
    """
    return rpc_utils.get_motd()


def get_static_data():
    """
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
    default_drone_set_name = models.DroneSet.default_drone_set_name()
    drone_sets = ([default_drone_set_name] +
                  sorted(drone_set.name for drone_set in
                         models.DroneSet.objects.exclude(
                             name=default_drone_set_name)))

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
        models.User.current_user().get_object_dict())
    result['host_statuses'] = sorted(models.Host.Status.names)
    result['job_statuses'] = sorted(models.HostQueueEntry.Status.names)
    result['job_timeout_default'] = models.Job.DEFAULT_TIMEOUT
    result['job_max_runtime_hrs_default'] = models.Job.DEFAULT_MAX_RUNTIME_HRS
    result['parse_failed_repair_default'] = bool(
        models.Job.DEFAULT_PARSE_FAILED_REPAIR)
    result['reboot_before_options'] = model_attributes.RebootBefore.names
    result['reboot_after_options'] = model_attributes.RebootAfter.names
    result['motd'] = rpc_utils.get_motd()
    result['drone_sets_enabled'] = models.DroneSet.drone_sets_enabled()
    result['drone_sets'] = drone_sets
    result['parameterized_jobs'] = models.Job.parameterized_jobs_enabled()

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
                                   "Waiting": "Waiting for scheduler action",
                                   "Archiving": "Archiving results"}
    return result


def get_server_time():
    """
    Return server current time.

    :return: Date string in format YYYY-MM-DD HH:MM
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def get_version():
    """
    Return autotest version.

    :return: String with version.
    """
    return version.get_version()


def get_interface_version():
    """
    Return interface version.

    :return: Sequence with year, month number, day.
    """
    return INTERFACE_VERSION


def _get_logs_used_space():
    """
    (Internal) Return disk usage (percentage) for the results directory.

    :return: Usage in percents (integer value).
    """
    logs_dir = settings.get_value('COMMON', 'test_output_dir', default=None)
    autodir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                           '..', '..'))
    if logs_dir is None:
        logs_dir = os.path.join(autodir, 'results')
    usage = psutil.disk_usage(logs_dir)
    return int(usage.percent)


def _process_running(process_name):
    """
    (Internal) Return whether a given process name is running.

    :param process_name: The name of the process.
    :return: True (running) or False (no).
    """
    process_running = False
    for p in psutil.process_iter():
        for args in p.cmdline:
            if os.path.basename(args) == process_name and p.is_running:
                process_running = True
    return process_running


def get_server_status():
    """
    Get autotest server system information.

    :return: Dict with keys:
             * 'disk_space_percentage' Autotest log directory disk usage
             * 'scheduler_running' Whether the autotest scheduler is running
             * 'sheduler_watcher_running' Whether the scheduler watcher is
                running
             * 'concerns' Global evaluation of whether there are problems to
                be addressed
    """
    server_status = {}
    concerns = False
    disk_treshold = int(settings.get_value('SERVER', 'logs_disk_usage_treshold',
                                           default="80"))
    used_space_logs = _get_logs_used_space()
    if used_space_logs > disk_treshold:
        concerns = True
    server_status['used_space_logs'] = used_space_logs
    scheduler_running = _process_running('autotest-scheduler')
    if not scheduler_running:
        concerns = True
    server_status['scheduler_running'] = scheduler_running
    watcher_running = _process_running('autotest-scheduler-watcher')
    if not watcher_running:
        concerns = True
    server_status['scheduler_watcher_running'] = watcher_running
    if settings.get_value('INSTALL_SERVER', 'xmlrpc_url', default=''):
        install_server_running = get_install_server_profiles() is not None
        if not install_server_running:
            concerns = True
    else:
        install_server_running = False
    server_status['install_server_running'] = install_server_running
    server_status['concerns'] = concerns
    return server_status
