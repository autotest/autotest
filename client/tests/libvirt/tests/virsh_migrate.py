import re, os, logging, commands, shutil, time
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import virt_vm, virt_utils, virt_env_process

def run_virsh_migrate(test, params, env):
    """
    Test the migrate command with parameter --live.
    """

    def do_migration(dly, vm, dest_uri, options, extra):
        logging.info("Sleeping %d seconds before migration" % dly)
        time.sleep(dly)
        # Migrate the guest.
        successful = vm.migrate(dest_uri, options, extra)
        if not successful:
            raise error.TestFail("Migration failed for %s." % vm_name)

        if vm.is_alive(): # vm.connect_uri was updated
            logging.info("Alive guest found on destination %s." % dest_uri)
        else:
            raise error.TestFail("VM not running on destination %s" % dest_uri)
        # FIXME: This needs to be tested, but won't work currently
        # vm.verify_kernel_crash()

    vm_name = params.get("main_vm")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    src_uri = vm.connect_uri
    dest_uri = params.get("virsh_migrate_desturi")
    # Identify easy config. mistakes early
    warning_text = "Migration VM %s %s appears problematic"+\
                    " this may lead to migration problems."+\
                    " Consider specifying vm.connect_uri using"+\
                    " fully-qualified network-based style."
    if src_uri.count('///') or src_uri.count('EXAMPLE'):
        logging.warning(warning_text % ('source', src_uri)
    if dest_uri.count('///') or dest_uri.count('EXAMPLE'):
        logging.warning(warning_text % ('destination', dest_uri)

    options = params.get("virsh_migrate_options")
    extra = params.get("virsh_migrate_extra")
    dly = int(params.get("virsh_migrate_delay", 10))

    
    do_migration(dly, vm, dest_uri, options, extra)
    # Repeat the migration with a recursive call and guaranteed exit
    if params.get("virsh_migrate_back", "no") == 'yes':
        back_dest_uri = params.get("virsh_migrate_back_desturi", 'default')
        back_options = params.get("virsh_migrate_back_options", 'default')
        back_extra = params.get("virsh_migrate_back_extra", 'default')
        if back_dest_uri == 'default':
            back_dest_uri = src_uri
        if back_options == 'default':
            back_options = options
        if back_extra == 'default':
            back_extra = extra
        do_migration(dly, vm, back_dest_uri, back_options, back_extra)
