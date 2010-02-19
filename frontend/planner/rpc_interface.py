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
from autotest_lib.frontend.planner import models, rpc_utils
from autotest_lib.client.common_lib import utils

# basic getter/setter calls
# TODO: deprecate the basic calls and reimplement them in the REST framework

def get_plan(id):
    return afe_rpc_utils.prepare_for_serialization(
            models.Plan.smart_get(id).get_object_dict())


def modify_plan(id, **data):
    models.Plan.smart_get(id).update_object(data)


# more advanced calls

def submit_plan(name, hosts, host_labels, tests,
                support=None, label_override=None):
    """
    Submits a plan to the Test Planner

    @param name: the name of the plan
    @param hosts: a list of hostnames
    @param host_labels: a list of host labels. The hosts under test will update
                        to reflect changes in the label
    @param tests: a list of test control files to run
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

    plan, created = models.Plan.objects.get_or_create(name=name)
    if not created:
        raise model_logic.ValidationError(
                {'name': 'Plan name %s already exists' % name})

    try:
        label = rpc_utils.create_plan_label(plan)
    except:
        plan.delete()
        raise

    plan.label_override = label_override
    plan.support = support or ''
    plan.save()

    plan.owners.add(afe_models.User.current_user())

    for host in host_objects:
        planner_host = models.Host.objects.create(plan=plan, host=host)

    plan.host_labels.add(*label_objects)

    rpc_utils.start_plan(plan, label)

    return plan.id


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
