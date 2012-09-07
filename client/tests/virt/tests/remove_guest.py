from autotest.client.shared import error


@error.context_aware
def run_remove_guest(test, params, env):
    """
    everything is done by client.virt module
    """
    pass
