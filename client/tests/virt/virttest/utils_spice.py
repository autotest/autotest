"""
Common spice test utility functions.

"""
import logging, time
from autotest.client.shared import error
from aexpect import ShellCmdError


def wait_timeout(timeout=10):
    """
    time.sleep(timeout) + logging.debug(timeout)

    @param timeout=10
    """
    logging.debug("Waiting (timeout=%ss)", timeout)
    time.sleep(timeout)


def start_vdagent(guest_session, test_timeout):
    """
    Sending commands to start the spice-vdagentd service

    @param guest_session: ssh session of the VM
    @param test_timeout: timeout time for the cmds
    """
    cmd = "service spice-vdagentd status"
    try:
        guest_session.cmd(cmd, print_func=logging.info,
                                   timeout=test_timeout)
    except ShellCmdError:
        guest_session.cmd("service spice-vdagentd start",
                                   print_func=logging.info,
                                   timeout=test_timeout)
    except:
        raise error.TestFail("Guest Vdagent Daemon Check failed")

    logging.debug("------------ End of guest checking for Spice Vdagent"
                  " Daemon ------------")

    # Wait for vdagent to come up
    wait_timeout(30)


def stop_vdagent(guest_session, test_timeout):
    """
    Sending commands to stop the spice-vdagentd service

    @param guest_session: ssh session of the VM
    @param test_timeout: timeout time for the cmds
    """
    cmd = "service spice-vdagentd stop"
    try:
        guest_session.cmd(cmd, print_func=logging.info,
                                   timeout=test_timeout)
    except ShellCmdError:
        raise error.TestFail("Couldn't turn off spice vdagent process")
    except:
        raise error.TestFail("Guest Vdagent Daemon Check failed")

    logging.debug("------------ End of guest checking for Spice Vdagent"
                  " Daemon ------------")


def verify_vdagent(guest_session, test_timeout):
    """
    Verifying vdagent is installed on a VM

    @param guest_session: ssh session of the VM
    @param test_timeout: timeout time for the cmds
    """
    cmd = "rpm -qa | grep spice-vdagent"

    try:
        guest_session.cmd(cmd, print_func=logging.info, timeout=test_timeout)
    finally:
        logging.debug("----------- End of guest check to see if vdagent package"
                     " is available ------------")


def verify_virtio(guest_session, test_timeout):
    """
    Verify Virtio linux driver is properly loaded.

    @param guest_session: ssh session of the VM
    @param test_timeout: timeout time for the cmds
    """
    #cmd = "lsmod | grep virtio_console"
    cmd = "ls /dev/virtio-ports/"
    try:
        guest_session.cmd(cmd, print_func=logging.info, timeout=test_timeout)
    finally:
        logging.debug("------------ End of guest check of the Virtio-Serial"
                     " Driver------------")
