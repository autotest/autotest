import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def internal_yum_update(session, command, prompt, timeout):
    """
    Helper function to perform the yum update test.

    @param session: shell session stablished to the host
    @param command: Command to be sent to the shell session
    @param prompt: Machine prompt
    @param timeout: How long to wait until we get an appropriate output from
            the shell session.
    """
    session.sendline(command)
    end_time = time.time() + timeout
    while time.time() < end_time:
        (match, text) = session.read_until_last_line_matches(
                        ["[Ii]s this [Oo][Kk]", prompt], timeout=timeout)
        if match == 0:
            logging.info("Got 'Is this ok'; sending 'y'")
            session.sendline("y")
        elif match == 1:
            logging.info("Got shell prompt")
            return True
        else:
            logging.info("Timeout or process exited")
            return False


def run_yum_update(test, params, env):
    """
    Runs yum update and yum update kernel on the remote host (yum enabled
    hosts only).

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    internal_yum_update(session, "yum update", params.get("shell_prompt"), 600)
    internal_yum_update(session, "yum update kernel",
                        params.get("shell_prompt"), 600)

    session.close()
