"""\
Functions to expose over the RPC interface.
"""

__author__ = 'jamesren@google.com (James Ren)'


import os, re
import common
from django.db import models as django_models
from autotest_lib.frontend import thread_local
from autotest_lib.frontend.afe import model_logic, models as afe_models
from autotest_lib.frontend.afe import rpc_utils as afe_rpc_utils
from autotest_lib.frontend.afe import rpc_interface as afe_rpc_interface
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.frontend.planner import models, rpc_utils, model_attributes
from autotest_lib.frontend.planner import failure_actions
from autotest_lib.client.common_lib import utils

# basic getter/setter calls
# TODO: deprecate the basic calls and reimplement them in the REST framework

def get_plan(id):
    return afe_rpc_utils.prepare_for_serialization(
            models.Plan.smart_get(id).get_object_dict())


def modify_plan(id, **data):
    models.Plan.smart_get(id).update_object(data)


def modify_test_run(id, **data):
    models.TestRun.objects.get(id=id).update_object(data)


def modify_host(id, **data):
    models.Host.objects.get(id=id).update_object(data)


def add_job(plan_id, test_config_id, afe_job_id):
    models.Job.objects.create(
            plan=models.Plan.objects.get(id=plan_id),
            test_config=models.TestConfig.objects.get(id=test_config_id),
            afe_job=afe_models.Job.objects.get(id=afe_job_id))


# more advanced calls

def submit_plan(name, hosts, host_labels, tests, support=None,
                label_override=None, additional_parameters=None):
    """
    Submits a plan to the Test Planner

    @param name: the name of the plan
    @param hosts: a list of hostnames
    @param host_labels: a list of host labels. The hosts under test will update
                        to reflect changes in the label
    @param tests: an ordered list of dictionaries:
                      alias: an alias for the test
                      control_file: the test control file
                      is_server: True if is a server-side control file
                      estimated_runtime: estimated number of hours this test
                                         will run
    @param support: the global support script
    @param label_override: label to prepend to all AFE jobs for this test plan.
                           Defaults to the plan name.
    @param additional_parameters: A mapping of AdditionalParameters to apply to
                                  this test plan, as an ordered list. Each item
                                  of the list is a dictionary:
                                  hostname_regex: A regular expression; the
                                                  additional parameter in the
                                                  value will be applied if the
                                                  hostname matches this regex
                                  param_type: The type of additional parameter
                                  param_values: A dictionary of key=value pairs
                                                for this parameter
               example:
               [{'hostname_regex': 'host[0-9]',
                 'param_type': 'Verify',
                 'param_values': {'key1': 'value1',
                                  'key2': 'value2'}},
                {'hostname_regex': '.*',
                 'param_type': 'Verify',
                 'param_values': {'key': 'value'}}]

                                  Currently, the only (non-site-specific)
                                  param_type available is 'Verify'. Setting
                                  these parameters allows the user to specify
                                  arguments to the
                                  job.run_test('verify_test', ...) line at the
                                  beginning of the wrapped control file for each
                                  test
    """
    host_objects = []
    label_objects = []

    for host in hosts or []:
        try:
            host_objects.append(
                    afe_models.Host.valid_objects.get(hostname=host))
        except afe_models.Host.DoesNotExist:
            raise model_logic.ValidationError(
                    {'hosts': 'host %s does not exist' % host})

    for label in host_labels or []:
        try:
            label_objects.append(afe_models.Label.valid_objects.get(name=label))
        except afe_models.Label.DoesNotExist:
            raise model_logic.ValidationError(
                    {'host_labels': 'host label %s does not exist' % label})

    aliases_seen = set()
    test_required_fields = (
            'alias', 'control_file', 'is_server', 'estimated_runtime')
    for test in tests:
        for field in test_required_fields:
            if field not in test:
                raise model_logic.ValidationError(
                        {'tests': 'field %s is required' % field})

        alias = test['alias']
        if alias in aliases_seen:
            raise model_logic.Validationerror(
                    {'tests': 'alias %s occurs more than once' % alias})
        aliases_seen.add(alias)

    plan, created = models.Plan.objects.get_or_create(name=name)
    if not created:
        raise model_logic.ValidationError(
                {'name': 'Plan name %s already exists' % name})

    try:
        rpc_utils.set_additional_parameters(plan, additional_parameters)
        label = rpc_utils.create_plan_label(plan)
        try:
            for i, test in enumerate(tests):
                control, _ = models.ControlFile.objects.get_or_create(
                        contents=test['control_file'])
                models.TestConfig.objects.create(
                        plan=plan, alias=test['alias'], control_file=control,
                        is_server=test['is_server'], execution_order=i,
                        estimated_runtime=test['estimated_runtime'])

            plan.label_override = label_override
            plan.support = support or ''
            plan.save()

            plan.owners.add(afe_models.User.current_user())

            for host in host_objects:
                planner_host = models.Host.objects.create(plan=plan, host=host)

            plan.host_labels.add(*label_objects)

            rpc_utils.start_plan(plan, label)

            return plan.id
        except:
            label.delete()
            raise
    except:
        plan.delete()
        raise


def get_hosts(plan_id):
    """
    Gets the hostnames of all the hosts in this test plan.

    Resolves host labels in the plan.
    """
    plan = models.Plan.smart_get(plan_id)

    hosts = set(plan.hosts.all().values_list('hostname', flat=True))
    for label in plan.host_labels.all():
        hosts.update(label.host_set.all().values_list('hostname', flat=True))

    return afe_rpc_utils.prepare_for_serialization(hosts)


def get_atomic_group_control_file():
    """
    Gets the control file to apply the atomic group for a set of machines
    """
    return rpc_utils.lazy_load(os.path.join(os.path.dirname(__file__),
                                            'set_atomic_group_control.srv'))


def get_next_test_configs(plan_id):
    """
    Gets information about the next planner test configs that need to be run

    @param plan_id: the ID or name of the test plan
    @return a dictionary:
                complete: True or False, shows test plan completion
                next_configs: a list of dictionaries:
                    host: ID of the host
                    next_test_config_id: ID of the next Planner test to run
    """
    plan = models.Plan.smart_get(plan_id)

    result = {'next_configs': []}

    rpc_utils.update_hosts_table(plan)
    for host in models.Host.objects.filter(plan=plan):
        next_test_config = rpc_utils.compute_next_test_config(plan, host)
        if next_test_config:
            config = {'next_test_config_id': next_test_config.id,
                      'next_test_config_alias': next_test_config.alias,
                      'host': host.host.hostname}
            result['next_configs'].append(config)

    rpc_utils.check_for_completion(plan)
    result['complete'] = plan.complete

    return result


def update_test_runs(plan_id):
    """
    Add all applicable TKO jobs to the Planner DB tables

    Looks for tests in the TKO tables that were started as a part of the test
    plan, and add them to the Planner tables.

    Also updates the status of the test run if the underlying TKO test move from
    an active status to a completed status.

    @return a list of dictionaries:
                status: the status of the new (or updated) test run
                tko_test_idx: the ID of the TKO test added
                hostname: the host added
    """
    plan = models.Plan.smart_get(plan_id)
    updated = []

    for planner_job in plan.job_set.all():
        known_statuses = dict((test_run.tko_test.test_idx, test_run.status)
                              for test_run in planner_job.testrun_set.all())
        tko_tests_for_job = tko_models.Test.objects.filter(
                job__afe_job_id=planner_job.afe_job.id)

        for tko_test in tko_tests_for_job:
            status = rpc_utils.compute_test_run_status(tko_test.status.word)
            needs_update = (tko_test.test_idx not in known_statuses or
                            status != known_statuses[tko_test.test_idx])
            if needs_update:
                hostnames = tko_test.machine.hostname.split(',')
                for hostname in hostnames:
                    rpc_utils.add_test_run(
                            plan, planner_job, tko_test, hostname, status)
                    updated.append({'status': status,
                                    'tko_test_idx': tko_test.test_idx,
                                    'hostname': hostname})

    return updated


def get_failures(plan_id):
    """
    Gets a list of the untriaged failures associated with this plan

    @return a list of dictionaries:
                id: the failure ID, for passing back to triage the failure
                group: the group for the failure. Normally the same as the
                       reason, but can be different for custom queries
                machine: the failed machine
                blocked: True if the failure caused the machine to block
                test_name: Concatenation of the Planner alias and the TKO test
                           name for the failed test
                reason: test failure reason
                seen: True if the failure is marked as "seen"
    """
    plan = models.Plan.smart_get(plan_id)
    result = {}

    failures = plan.testrun_set.filter(
            finalized=True, triaged=False,
            status=model_attributes.TestRunStatus.FAILED)
    failures = failures.order_by('seen').select_related('test_job__test',
                                                        'host__host',
                                                        'tko_test')
    for failure in failures:
        test_name = '%s: %s' % (
                failure.test_job.test_config.alias, failure.tko_test.test)

        group_failures = result.setdefault(failure.tko_test.reason, [])
        failure_dict = {'id': failure.id,
                        'machine': failure.host.host.hostname,
                        'blocked': bool(failure.host.blocked),
                        'test_name': test_name,
                        'reason': failure.tko_test.reason,
                        'seen': bool(failure.seen)}
        group_failures.append(failure_dict)

    return result


def get_test_runs(**filter_data):
    """
    Gets a list of test runs that match the filter data.

    Returns a list of expanded TestRun object dictionaries. Specifically, the
    "host" and "test_job" fields are expanded. Additionally, the "test_config"
    field of the "test_job" expansion is also expanded.
    """
    result = []
    for test_run in models.TestRun.objects.filter(**filter_data):
        test_run_dict = test_run.get_object_dict()
        test_run_dict['host'] = test_run.host.get_object_dict()
        test_run_dict['test_job'] = test_run.test_job.get_object_dict()
        test_run_dict['test_job']['test_config'] = (
                test_run.test_job.test_config.get_object_dict())
        result.append(test_run_dict)
    return result


def skip_test(test_config_id, hostname):
    """
    Marks a test config as "skipped" for a given host
    """
    config = models.TestConfig.objects.get(id=test_config_id)
    config.skipped_hosts.add(afe_models.Host.objects.get(hostname=hostname))


def mark_failures_as_seen(failure_ids):
    """
    Marks a set of failures as 'seen'

    @param failure_ids: A list of failure IDs, as returned by get_failures(), to
                        mark as seen
    """
    models.TestRun.objects.filter(id__in=failure_ids).update(seen=True)


def process_failures(failure_ids, host_action, test_action, labels=(),
                     keyvals=None, bugs=(), reason=None, invalidate=False):
    """
    Triage a failure

    @param failure_id: The failure ID, as returned by get_failures()
    @param host_action: One of 'Block', 'Unblock', 'Reinstall'
    @param test_action: One of 'Skip', 'Rerun'

    @param labels: Test labels to apply, by name
    @param keyvals: Dictionary of job keyvals to add (or replace)
    @param bugs: List of bug IDs to associate with this failure
    @param reason: An override for the test failure reason
    @param invalidate: True if failure should be invalidated for the purposes of
                       reporting. Defaults to False.
    """
    host_choices = failure_actions.HostAction.values
    test_choices = failure_actions.TestAction.values
    if host_action not in host_choices:
        raise model_logic.ValidationError(
                {'host_action': ('host action %s not valid; must be one of %s'
                                 % (host_action, ', '.join(host_choices)))})
    if test_action not in test_choices:
        raise model_logic.ValidationError(
                {'test_action': ('test action %s not valid; must be one of %s'
                                 % (test_action, ', '.join(test_choices)))})

    for failure_id in failure_ids:
        rpc_utils.process_failure(
                failure_id=failure_id, host_action=host_action,
                test_action=test_action, labels=labels, keyvals=keyvals,
                bugs=bugs, reason=reason, invalidate=invalidate)


def get_machine_view_data(plan_id):
    """
    Gets the data required for the web frontend Machine View.

    @param plan_id: The ID of the test plan
    @return An array. Each element is a dictionary:
                    machine: The name of the machine
                    status: The machine's status (one of
                            model_attributes.HostStatus)
                    bug_ids: List of the IDs for the bugs filed
                    tests_run: An array of dictionaries:
                            test_name: The TKO name of the test
                            success: True if the test passed
    """
    plan = models.Plan.smart_get(plan_id)
    result = []
    for host in plan.host_set.all():
        tests_run = []

        machine = host.host.hostname
        host_status = host.status()
        bug_ids = set()

        testruns = plan.testrun_set.filter(host=host, invalidated=False,
                                           finalized=True)
        for testrun in testruns:
            test_name = testrun.tko_test.test
            test_status = testrun.tko_test.status.word
            testrun_bug_ids = testrun.bugs.all().values_list(
                    'external_uid', flat=True)

            tests_run.append({'test_name': test_name,
                              'status': test_status})
            bug_ids.update(testrun_bug_ids)

        result.append({'machine': machine,
                       'status': host_status,
                       'tests_run': tests_run,
                       'bug_ids': list(bug_ids)})
    return result


def generate_test_config(alias, afe_test_name=None,
                         estimated_runtime=0, **kwargs):
    """
    Creates and returns a test config suitable for passing into submit_plan()

    Also accepts optional parameters to pass directly in to the AFE RPC
    interface's generate_control_file() method.

    @param alias: The alias for the test
    @param afe_test_name: The name of the test, as shown on AFE
    @param estimated_runtime: Estimated number of hours this test is expected to
                              run. For reporting purposes.
    """
    if afe_test_name is None:
        afe_test_name = alias
    alias = alias.replace(' ', '_')

    control = afe_rpc_interface.generate_control_file(tests=[afe_test_name],
                                                      **kwargs)

    return {'alias': alias,
            'control_file': control['control_file'],
            'is_server': control['is_server'],
            'estimated_runtime': estimated_runtime}


def get_wrapped_test_config(id, hostname, run_verify):
    """
    Gets the TestConfig object identified by the ID

    Returns the object dict of the TestConfig, plus an additional
    'wrapped_control_file' value, which includes the pre-processing that the
    ControlParameters specify.

    @param hostname: Hostname of the machine this test config will run on
    @param run_verify: Set to True or False to override the default behavior
                       (which is to run the verify test unless the skip_verify
                       ControlParameter is set)
    """
    test_config = models.TestConfig.objects.get(id=id)
    object_dict = test_config.get_object_dict()
    object_dict['control_file'] = test_config.control_file.get_object_dict()
    object_dict['wrapped_control_file'] = rpc_utils.wrap_control_file(
            plan=test_config.plan, hostname=hostname,
            run_verify=run_verify, test_config=test_config)

    return object_dict


def generate_additional_parameters(hostname_regex, param_type, param_values):
    """
    Generates an AdditionalParamter dictionary, for passing in to submit_plan()

    Returns a dictionary. To use in submit_job(), put this dictionary into a
    list (possibly with other additional_parameters dictionaries)

    @param hostname_regex: The hostname regular expression to match
    @param param_type: One of get_static_data()['additional_parameter_types']
    @param param_values: Dictionary of key=value pairs for this parameter
    """
    try:
        re.compile(hostname_regex)
    except Exception:
        raise model_logic.ValidationError(
                {'hostname_regex': '%s is not a valid regex' % hostname_regex})

    if param_type not in model_attributes.AdditionalParameterType.values:
        raise model_logic.ValidationError(
                {'param_type': '%s is not a valid parameter type' % param_type})

    if type(param_values) is not dict:
        raise model_logic.ValidationError(
                {'param_values': '%s is not a dictionary' % repr(param_values)})

    return {'hostname_regex': hostname_regex,
            'param_type': param_type,
            'param_values': param_values}


def get_overview_data(plan_ids):
    """
    Gets the data for the Overview tab

    @param plan_ids: A list of the plans, by id or name
    @return A dictionary - keys are plan names, values are dictionaries of data:
                machines: A list of dictionaries:
                hostname: The machine's hostname
                status: The host's status
                passed: True if the machine passed the test plan. A 'pass' means
                        that, for every test configuration in the plan, the
                        machine had at least one AFE job with no failed tests.
                        'passed' could also be None, meaning that this host is
                        still running tests.
                bugs: A list of the bugs filed
                test_configs: A list of dictionaries, each representing a test
                              config:
                    complete: Number of hosts that have completed this test
                              config
                    estimated_runtime: Number of hours this test config is
                                       expected to run on each host
    """
    plans = models.Plan.smart_get_bulk(plan_ids)
    result = {}

    for plan in plans:
        machines = []
        for host in plan.host_set.all():
            pass_status = rpc_utils.compute_test_config_status(host)
            if pass_status == rpc_utils.ComputeTestConfigStatusResult.PASS:
                passed = True
            elif pass_status == rpc_utils.ComputeTestConfigStatusResult.FAIL:
                passed = False
            else:
                passed = None
            machines.append({'hostname': host.host.hostname,
                             'status': host.status(),
                             'passed': passed})

        bugs = set()
        for testrun in plan.testrun_set.all():
            bugs.update(testrun.bugs.values_list('external_uid', flat=True))

        test_configs = []
        for test_config in plan.testconfig_set.all():
            complete_jobs = test_config.job_set.filter(
                    afe_job__hostqueueentry__complete=True)
            complete_afe_jobs = afe_models.Job.objects.filter(
                    id__in=complete_jobs.values_list('afe_job', flat=True))

            complete_hosts = afe_models.Host.objects.filter(
                    hostqueueentry__job__in=complete_afe_jobs)
            complete_hosts |= test_config.skipped_hosts.all()

            test_configs.append(
                    {'complete': complete_hosts.distinct().count(),
                     'estimated_runtime': test_config.estimated_runtime})

        plan_data = {'machines': machines,
                     'bugs': list(bugs),
                     'test_configs': test_configs}
        result[plan.name] = plan_data

    return result


def get_test_view_data(plan_id):
    """
    Gets the data for the Test View tab

    @param plan_id: The name or ID of the test plan
    @return A dictionary - Keys are test config aliases, values are dictionaries
                           of data:
                total_machines: Total number of machines scheduled for this test
                                config. Excludes machines that are set to skip
                                this config.
                machine_status: A dictionary:
                    key: The hostname
                    value: The status of the machine: one of 'Scheduled',
                           'Running', 'Pass', or 'Fail'
                total_runs: Total number of runs of this test config. Includes
                            repeated runs (from triage re-run)
                total_passes: Number of runs that resulted in a 'pass', meaning
                              that none of the tests in the test config had any
                              status other than GOOD.
                bugs: List of bugs that were filed under this test config
    """
    plan = models.Plan.smart_get(plan_id)
    result = {}
    for test_config in plan.testconfig_set.all():
        skipped_host_ids = test_config.skipped_hosts.values_list('id',
                                                                 flat=True)
        hosts = plan.host_set.exclude(host__id__in=skipped_host_ids)
        total_machines = hosts.count()

        machine_status = {}
        for host in hosts:
            machine_status[host.host.hostname] = (
                    rpc_utils.compute_test_config_status(host, test_config))

        planner_jobs = test_config.job_set.all()
        total_runs = planner_jobs.count()
        total_passes = 0
        for planner_job in planner_jobs:
            if planner_job.all_tests_passed():
                total_passes += 1

        test_runs = plan.testrun_set.filter(
                test_job__in=test_config.job_set.all())
        bugs = set()
        for test_run in test_runs:
            bugs.update(test_run.bugs.values_list('external_uid', flat=True))

        result[test_config.alias] = {'total_machines': total_machines,
                                     'machine_status': machine_status,
                                     'total_runs': total_runs,
                                     'total_passes': total_passes,
                                     'bugs': list(bugs)}
    return result


def get_motd():
    return afe_rpc_utils.get_motd()


def get_static_data():
    result = {'motd': get_motd(),
              'host_actions': sorted(failure_actions.HostAction.values),
              'test_actions': sorted(failure_actions.TestAction.values),
              'additional_parameter_types':
                      sorted(model_attributes.AdditionalParameterType.values),
              'host_statuses': sorted(model_attributes.HostStatus.values)}
    return result
