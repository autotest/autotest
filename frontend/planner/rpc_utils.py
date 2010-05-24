import common
import os
from autotest_lib.frontend.afe import models as afe_models, model_logic
from autotest_lib.frontend.planner import models, model_attributes
from autotest_lib.frontend.planner import failure_actions, control_file
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.client.common_lib import global_config, utils, global_config
from autotest_lib.client.common_lib import enum


PLANNER_LABEL_PREFIX = 'planner_'
PLANNER_ATOMIC_GROUP_NAME = 'planner_global_atomic_group'
SERVER = global_config.global_config.get_config_value('SERVER', 'hostname')
LAZY_LOADED_FILES = {}


def create_plan_label(plan):
    """
    Creates the host label to apply on the plan hosts
    """
    group, _ = afe_models.AtomicGroup.objects.get_or_create(
            name=PLANNER_ATOMIC_GROUP_NAME)
    if group.invalid:
        group.invalid = False
        group.save()

    name = PLANNER_LABEL_PREFIX + plan.name
    if bool(afe_models.Label.valid_objects.filter(name=name)):
        raise model_logic.ValidationError('Label %s already exists, '
                                          'cannot start plan' % name)
    label = afe_models.Label(name=name, atomic_group=group)
    label.save()

    return label


def start_plan(plan, label):
    """
    Takes the necessary steps to start a test plan in Autotest
    """
    timeout = global_config.global_config.get_config_value(
            'PLANNER', 'execution_engine_timeout')
    control = _get_execution_engine_control(
            server=SERVER,
            plan_id=plan.id,
            label_name=label.name,
            owner=afe_models.User.current_user().login)
    options = {'name': plan.name + '_execution_engine',
               'priority': afe_models.Job.Priority.MEDIUM,
               'control_file': control,
               'control_type': afe_models.Job.ControlType.SERVER,
               'synch_count': None,
               'timeout': timeout,
               'max_runtime_hrs': timeout,
               'run_verify': False,
               'reboot_before': False,
               'reboot_after': False,
               'dependencies': ()}
    job = afe_models.Job.create(owner=afe_models.User.current_user().login,
                                options=options, hosts=())
    job.queue(hosts=())


def _get_execution_engine_control(server, plan_id, label_name, owner):
    """
    Gets the control file to run the execution engine
    """
    control = lazy_load(os.path.join(os.path.dirname(__file__),
                                     'execution_engine_control.srv'))
    return control % dict(server=server, plan_id=plan_id,
                          label_name=label_name, owner=owner)


def lazy_load(path):
    """
    Lazily loads the file indicated by the path given, and caches the result
    """
    if path not in LAZY_LOADED_FILES:
        LAZY_LOADED_FILES[path] = utils.read_file(path)

    return LAZY_LOADED_FILES[path]


def update_hosts_table(plan):
    """
    Resolves the host labels into host objects

    Adds or removes hosts from the planner Hosts model based on changes to the
    host label
    """
    label_hosts = set()

    for label in plan.host_labels.all():
        for afe_host in label.host_set.all():
            host, created = models.Host.objects.get_or_create(plan=plan,
                                                              host=afe_host)
            if created:
                host.added_by_label = True
                host.save()

            label_hosts.add(host.host.id)

    deleted_hosts = models.Host.objects.filter(
            plan=plan, added_by_label=True).exclude(host__id__in=label_hosts)
    deleted_hosts.delete()


def compute_next_test_config(plan, host):
    """
    Gets the next test config that should be run for this plan and host

    Returns None if the host is already running a job. Also sets the host's
    complete bit if the host is finished running tests.
    """
    if host.blocked:
        return None

    test_configs = plan.testconfig_set.exclude(
            skipped_hosts=host.host).order_by('execution_order')
    result = None

    for test_config in test_configs:
        planner_jobs = test_config.job_set.filter(
                afe_job__hostqueueentry__host=host.host)
        for planner_job in planner_jobs:
            if planner_job.active():
                # There is a job active; do not start another one
                return None
        try:
            planner_job = planner_jobs.get(requires_rerun=False)
        except models.Job.DoesNotExist:
            if not result:
                result = test_config

    if result:
        return result

    # All jobs related to this host are complete
    host.complete = True
    host.save()
    return None


def check_for_completion(plan):
    """
    Checks if a plan is actually complete. Sets complete=True if so
    """
    if not models.Host.objects.filter(plan=plan, complete=False):
        plan.complete = True
        plan.save()


def compute_test_run_status(status):
    """
    Converts a TKO test status to a Planner test run status
    """
    Status = model_attributes.TestRunStatus
    if status == 'GOOD':
        return Status.PASSED
    if status == 'RUNNING':
        return Status.ACTIVE
    return Status.FAILED


def add_test_run(plan, planner_job, tko_test, hostname, status):
    """
    Adds a TKO test to the Planner Test Run tables
    """
    host = afe_models.Host.objects.get(hostname=hostname)

    planner_host = models.Host.objects.get(plan=plan, host=host)
    test_run, _ = models.TestRun.objects.get_or_create(plan=plan,
                                                       test_job=planner_job,
                                                       tko_test=tko_test,
                                                       host=planner_host)
    test_run.status = status
    test_run.save()


def process_failure(failure_id, host_action, test_action, labels, keyvals,
                    bugs, reason, invalidate):
    if keyvals is None:
        keyvals = {}

    failure = models.TestRun.objects.get(id=failure_id)

    _process_host_action(failure.host, host_action)
    _process_test_action(failure.test_job, test_action)

    # Add the test labels
    for label in labels:
        tko_test_label, _ = (
                tko_models.TestLabel.objects.get_or_create(name=label))
        failure.tko_test.testlabel_set.add(tko_test_label)

    # Set the job keyvals
    for key, value in keyvals.iteritems():
        keyval, created = tko_models.JobKeyval.objects.get_or_create(
                job=failure.tko_test.job, key=key)
        if not created:
            tko_models.JobKeyval.objects.create(job=failure.tko_test.job,
                                                key='original_' + key,
                                                value=keyval.value)
        keyval.value = value
        keyval.save()

    # Add the bugs
    for bug_id in bugs:
        bug, _ = models.Bug.objects.get_or_create(external_uid=bug_id)
        failure.bugs.add(bug)

    # Set the failure reason
    if reason is not None:
        tko_models.TestAttribute.objects.create(test=failure.tko_test,
                                                attribute='original_reason',
                                                value=failure.tko_test.reason)
        failure.tko_test.reason = reason
        failure.tko_test.save()

    # Set 'invalidated', 'seen', and 'triaged'
    failure.invalidated = invalidate
    failure.seen = True
    failure.triaged = True
    failure.save()


def _site_process_host_action_dummy(host, action):
    return False


def _process_host_action(host, action):
    """
    Takes the specified action on the host
    """
    HostAction = failure_actions.HostAction
    if action not in HostAction.values:
        raise ValueError('Unexpected host action %s' % action)

    site_process = utils.import_site_function(
            __file__, 'autotest_lib.frontend.planner.site_rpc_utils',
            'site_process_host_action', _site_process_host_action_dummy)

    if not site_process(host, action):
        # site_process_host_action returns True and and only if it matched a
        # site-specific processing option
        if action == HostAction.BLOCK:
            host.blocked = True
        elif action == HostAction.UNBLOCK:
            host.blocked = False
        else:
            assert action == HostAction.REINSTALL
            raise NotImplemented('TODO: implement reinstall')

        host.save()


def _process_test_action(planner_job, action):
    """
    Takes the specified action for this planner job
    """
    TestAction = failure_actions.TestAction
    if action not in TestAction.values:
        raise ValueError('Unexpected test action %s' % action)

    if action == TestAction.SKIP:
        # Do nothing
        pass
    else:
        assert action == TestAction.RERUN
        planner_job.requires_rerun = True
        planner_job.save()


def set_additional_parameters(plan, additional_parameters):
    if not additional_parameters:
        return

    for index, additional_parameter in enumerate(additional_parameters):
        hostname_regex = additional_parameter['hostname_regex']
        param_type = additional_parameter['param_type']
        param_values = additional_parameter['param_values']

        additional_param = models.AdditionalParameter.objects.create(
                plan=plan, hostname_regex=hostname_regex,
                param_type=param_type, application_order=index)

        for key, value in param_values.iteritems():
            models.AdditionalParameterValue.objects.create(
                    additional_parameter=additional_param,
                    key=key, value=repr(value))


def _additional_wrap_arguments_dummy(plan, hostname):
    return {}


def get_wrap_arguments(plan, hostname, param_type):
    additional_param = (
            models.AdditionalParameter.find_applicable_additional_parameter(
                    plan=plan, hostname=hostname, param_type=param_type))
    if not additional_param:
        return {}

    param_values = additional_param.additionalparametervalue_set.values_list(
            'key', 'value')
    return dict(param_values)


def wrap_control_file(plan, hostname, run_verify, test_config):
    """
    Wraps a control file using the ControlParameters for the plan
    """
    site_additional_wrap_arguments = utils.import_site_function(
            __file__, 'autotest_lib.frontend.planner.site_rpc_utils',
            'additional_wrap_arguments', _additional_wrap_arguments_dummy)
    additional_wrap_arguments = site_additional_wrap_arguments(plan, hostname)

    verify_params = get_wrap_arguments(
            plan, hostname, model_attributes.AdditionalParameterType.VERIFY)

    return control_file.wrap_control_file(
            control_file=test_config.control_file.contents,
            is_server=test_config.is_server,
            skip_verify=(not run_verify),
            verify_params=verify_params,
            **additional_wrap_arguments)


ComputeTestConfigStatusResult = enum.Enum('Pass', 'Fail', 'Scheduled',
                                          'Running', string_values=True)
def compute_test_config_status(host, test_config=None):
    """
    Returns a value of ComputeTestConfigStatusResult:
        Pass: This host passed the test config
        Fail: This host failed the test config
        Scheduled: This host has not yet run this test config
        Running: This host is currently running this test config

    A 'pass' means that, for every test configuration in the plan, the machine
    had at least one AFE job with no failed tests. 'passed' could also be None,
    meaning that this host is still running tests.

    @param test_config: A test config to check. None to check all test configs
                        in the plan
    """
    if test_config:
        test_configs = [test_config]
    else:
        test_configs = host.plan.testconfig_set.exclude(skipped_hosts=host.host)

    for test_config in test_configs:
        try:
            planner_job = test_config.job_set.get(
                    afe_job__hostqueueentry__host=host.host,
                    requires_rerun=False)
        except models.Job.DoesNotExist:
            return ComputeTestConfigStatusResult.SCHEDULED

        if planner_job.active():
            return ComputeTestConfigStatusResult.RUNNING

        if planner_job.testrun_set.exclude(tko_test__status__word='GOOD'):
            return ComputeTestConfigStatusResult.FAIL

    return ComputeTestConfigStatusResult.PASS
