"""\
Functions to expose over the RPC interface.
"""

__author__ = 'jamesren@google.com (James Ren)'


import os
import common
from django.db import models as django_models
from autotest_lib.frontend import thread_local
from autotest_lib.frontend.afe import model_logic, models as afe_models
from autotest_lib.frontend.afe import rpc_utils as afe_rpc_utils
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.frontend.planner import models, rpc_utils, model_attributes
from autotest_lib.client.common_lib import utils

# basic getter/setter calls
# TODO: deprecate the basic calls and reimplement them in the REST framework

def get_plan(id):
    return afe_rpc_utils.prepare_for_serialization(
            models.Plan.smart_get(id).get_object_dict())


def modify_plan(id, **data):
    models.Plan.smart_get(id).update_object(data)


def get_test_runs(**filter_data):
    return afe_rpc_utils.prepare_for_serialization(
            [test_run.get_object_dict() for test_run
             in models.TestRun.objects.filter(**filter_data)])


def modify_test_run(id, **data):
    models.TestRun.objects.get(id=id).update_object(data)


def modify_host(id, **data):
    models.Host.objects.get(id=id).update_object(data)


def get_test_config(id):
    return afe_rpc_utils.prepare_rows_as_nested_dicts(
            models.TestConfig.objects.filter(id=id), ('control_file',))[0]


def add_job(plan_id, test_config_id, afe_job_id):
    models.Job.objects.create(
            plan=models.Plan.objects.get(id=plan_id),
            test_config=models.TestConfig.objects.get(id=test_config_id),
            afe_job=afe_models.Job.objects.get(id=afe_job_id))


# more advanced calls

def submit_plan(name, hosts, host_labels, tests,
                support=None, label_override=None):
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
    @param support: the global support object
    @param label_override: label to prepend to all AFE jobs for this test plan.
                           Defaults to the plan name.
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
        next_test_config_id = rpc_utils.compute_next_test_config(plan, host)
        if next_test_config_id:
            config = {'next_test_config_id': next_test_config_id,
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
    plan = models.Plan.objects.get(id=plan_id)
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
    failures = failures.select_related('test_job__test', 'host__host',
                                       'tko_test')
    for failure in failures:
        test_name = '%s:%s' % (
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


def get_static_data():
    result = {'motd': afe_rpc_utils.get_motd()}
    return result
