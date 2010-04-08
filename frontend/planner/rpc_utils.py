import common
import os
from autotest_lib.frontend.afe import models as afe_models, model_logic
from autotest_lib.frontend.planner import models, model_attributes
from autotest_lib.client.common_lib import global_config, utils


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
    keyvals = {'server': SERVER,
               'plan_id': plan.id,
               'label_name': label.name}
    options = {'name': plan.name + '_execution_engine',
               'priority': afe_models.Job.Priority.MEDIUM,
               'control_file': _get_execution_engine_control(),
               'control_type': afe_models.Job.ControlType.SERVER,
               'synch_count': None,
               'run_verify': False,
               'reboot_before': False,
               'reboot_after': False,
               'dependencies': (),
               'keyvals': keyvals}
    job = afe_models.Job.create(owner=afe_models.User.current_user().login,
                                options=options, hosts=())
    job.queue(hosts=())


def _get_execution_engine_control():
    """
    Gets the control file to run the execution engine
    """
    return lazy_load(os.path.join(os.path.dirname(__file__),
                                  'execution_engine_control.srv'))


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

    test_configs = plan.testconfig_set.order_by('execution_order')
    for test_config in test_configs:
        afe_jobs = plan.job_set.filter(test_config=test_config)
        afe_job_ids = afe_jobs.values_list('afe_job', flat=True)
        hqes = afe_models.HostQueueEntry.objects.filter(job__id__in=afe_job_ids,
                                                        host=host.host)
        if not hqes and not bool(test_config.skipped_hosts.filter(host=host)):
            return test_config
        for hqe in hqes:
            if not hqe.complete:
                # HostQueueEntry still active for this host,
                # should not run another test
                return None

    # All HQEs related to this host are complete
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
