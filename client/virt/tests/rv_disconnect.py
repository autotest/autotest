"""
rv_disconnect.py - disconnect remote-viewer

Requires: connected binaries remote-viewer, Xorg, gnome session

"""
import logging, os

def run_rv_disconnect(test, params, env):
    """
    Tests disconnection of remote-viewer.

    @param test: KVM test object.  @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """

    guest_vm = env.get_vm(params["guest_vm"])
    guest_vm.verify_alive()
    guest_session = guest_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))

    client_vm = env.get_vm(params["client_vm"])
    client_vm.verify_alive()
    client_session = client_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))

    #get PID of remote-viewer and kill it
    logging.info("Get PID of remote-viewer")
    client_session.cmd("pgrep remote-viewer")

    logging.info("Try to kill remote-viewer")
    client_session.cmd("pkill %s" % params.get("rv_binary")\
                            .split(os.path.sep)[-1])

    guest_vm.verify_alive()

    client_session.close()
    guest_session.close()
