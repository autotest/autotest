import common
import os
from autotest_lib.frontend.afe import models as afe_models, model_logic
from autotest_lib.frontend.planner import models
from autotest_lib.frontend.shared import rest_client
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
    afe_rest = rest_client.Resource.load(
            'http://%s/afe/server/resources' % SERVER)

    keyvals = {'server': SERVER,
               'plan_id': plan.id,
               'label_name': label.name}

    info = afe_rest.execution_info.get().execution_info
    info['control_file'] = _get_execution_engine_control()
    info['machines_per_execution'] = None

    job_req = {'name': plan.name + '_execution_engine',
               'execution_info': info,
               'queue_entries': (),
               'keyvals': keyvals}

    afe_rest.jobs.post(job_req)


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
