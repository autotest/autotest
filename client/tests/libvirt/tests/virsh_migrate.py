import re, os, logging, commands, shutil
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import virt_vm, virt_utils, virt_env_process

def run_virsh_migrate(test, params, env):
    """
    Test the migrate command with parameter --live.
    """

    vm_name = params.get("main_vm")
    vm = env.get_vm(params["main_vm"])
    desturi = params.get("virsh_migrate_desturi")
    vm.verify_alive()

    # Migrate the guest.
    ret = vm.migrate()
    if ret == False:
        raise error.TestFail("Migration command failed for %s." % vm_name)

    if vm.is_alive():
        raise error.TestFail("VM %s found running on %s" %
                             (vm_name, vm.connect_uri))
    # libvirt guaranteed to be running on remote uri, exploit for verification
    # and optional destruction
    vm.connect_uri = desturi
    if vm.is_alive():
        logging.info("Alive guest %s found on destination %s." %
                     (vm_name, desturi))
        if params.get("kill_vm") == "yes":
            vm.destroy()
    else:
        raise error.TestFail("VM %s not running on destination %s" %
                             (vm_name, desturi))
