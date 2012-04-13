import logging, time
from autotest.client.shared import error
from autotest.client.virt import virt_utils


@error.context_aware
def run_remove_guest(test, params, env):
    """
    everything is done by client.virt module
    """
