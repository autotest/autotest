import logging
from autotest.client.shared import error
from autotest.client.virt import virt_agent


def run_guest_agent(test, params, env):
    """
    Test guest agent, this case will:
    1) Start VM with virtio serial port which named org.qemu.guest_agent.0.
    2) Install qemu-guest-agent package in guest.
    3) Create GuestAgent object and test if virt agent works.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environmen.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))

    # Try to install 'qemu-guest-agent' package.
    gagent_install_cmd = params.get("gagent_install_cmd")
    s = session.cmd_status(gagent_install_cmd)
    session.close()
    if s != 0:
        raise error.TestError("Could not install qemu-guest-agent package")

    gagent_name = "org.qemu.guest_agent.0"
    gagent_file_name = vm.get_virtio_port_filename(gagent_name)
    gagent = virt_agent.GuestAgent(gagent_name, gagent_file_name)

    # Check if guest agent work.
    gagent.verify_responsive()
    logging.info(gagent.cmd("guest-info"))
