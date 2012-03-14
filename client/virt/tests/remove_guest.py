import logging, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils


@error.context_aware
def run_remove_guest(test, params, env):
    """
    everything is done by client.virt module
    """
