import re, os, logging, commands, shutil, time
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import virt_vm, virt_utils, virt_env_process

def run_virsh_migrate(test, params, env):
    """
    Test the migrate command with parameter --live.
    """

    vm_name = params.get("main_vm")
    dest_host = params.get("virsh_migrate_desthost")
    protocol = params.get("virsh_migrate_proto", "qemu+ssh")
    options = params.get("virsh_migrate_options")
    extra = params.get("virsh_migrate_extra")
    destuser = params.get("virsh_migrate_destuser", "root")
    destpwd = params.get("virsh_migrate_destpwd", "")
    dly = int(params.get("virsh_migrate_delay", 10))

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    logging.info("Sleeping %d seconds before migration" % dly)
    time.sleep(dly)
    # Migrate the guest.
    successful = vm.migrate(dest_host, protocol, options, extra)
    if not successful:
        raise error.TestFail("Migration failed for %s." % vm_name)

    if vm.is_alive():
        raise error.TestFail("VM %s still running on %s after migration" %
                             (vm_name, vm.connect_uri))
    # libvirt guaranteed to be running on remote uri, exploit for verification
    # and optional destruction or subsequent tests with same VM instance
    orig_uri = vm.connect_uri
    vm.connect_uri = "%s://%s/system" % (protocol,dest_host)
    if vm.is_alive():
        logging.info("Alive guest %s found on destination %s." %
                     (vm_name, dest_host))
    else:
        vm.connect_uri = orig_uri
        raise error.TestFail("VM %s is not running on destination %s" %
                             (vm_name, dest_host))
    # FIXME: This needs to be tested, but won't work currently
    # vm.verify_kernel_crash()
