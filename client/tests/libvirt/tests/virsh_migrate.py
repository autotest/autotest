import re, os, logging, commands, shutil
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import virt_vm, virt_utils, virt_env_process

def run_virsh_migrate(test, params, env):
    """
    Test the migrate command with parameter --live.
    """

    vm_name = params.get("main_vm")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    destuser = params.get("virsh_migrate_destuser")
    destpwd = params.get("virsh_migrate_destpwd")
    destip = params.get("virsh_migrate_destip")
    destprompt = params.get("virsh_migrate_destprompt")

    # Migrate the guest.
    ret = vm.migrate()
    if ret == False:
        raise error.TestFail("Migration of %s failed." % vm_name)

    session = virt_utils.remote_login("ssh", destip, "22", destuser, destpwd, destprompt)
    status, output = session.cmd_status_output("virsh domstate %s" % vm_name)
    logging.info("Out put of virsh domstate %s: %s" % (vm_name, output))

    if status == 0 and output.find("running") >= 0:
        logging.info("Running guest %s is found on destination." % vm_name)
        session.cmd("virsh destroy %s" % vm_name)
    else:
        raise error.TestFail("Destination has no running guest named %s." % vm_name)
