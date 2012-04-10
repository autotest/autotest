import logging, time
from autotest_lib.client.common_lib import error

def run_virsh_migrate(test, params, env):
    """
    Test virsh migrate command.
    """

    def check_vm_state(vm, state):
        """
        Return True if vm is in the correct state.
        """
        actual_state = vm.state()
        if cmp(actual_state, state) == 0:
            return True
        else:
            return False

    def cleanup_dest(vm, src_uri = ""):
        """
        Clean up the destination host environment
        when doing the uni-direction migration.
        """
        vm_state = vm.state()
        if vm_state == "running":
            vm.destroy()
        elif vm_state == "paused":
            vm.resume()
            vm.destroy()

        if vm.is_persistent():
            vm.undefine()

        vm.connect_uri = src_uri

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

        # Migration may fail, but VM is alive on destination.
        dest_state = params.get("virsh_migrate_dest_state")
        ret = check_vm_state(vm, dest_state)
        logging.info("Supposed state: %s" % dest_state)
        logging.info("Actual state: %s" % vm.state())
        if not ret:
            raise error.TestFail("VM is not in the supposed state.")

        # FIXME: This needs to be tested, but won't work currently
        # vm.verify_kernel_crash()

    vm_name = params.get("main_vm")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    src_uri = vm.connect_uri
    dest_uri = params.get("virsh_migrate_desturi")
    # Identify easy config. mistakes early
    warning_text = ("Migration VM %s URI %s appears problematic "
                    "this may lead to migration problems. "
                    "Consider specifying vm.connect_uri using "
                    "fully-qualified network-based style.")

    if src_uri.count('///') or src_uri.count('EXAMPLE'):
        logging.warning(warning_text % ('source', src_uri))

    if dest_uri.count('///') or dest_uri.count('EXAMPLE'):
        logging.warning(warning_text % ('destination', dest_uri))

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
    # Do the uni-direction migration here.
    else:
        cleanup_dest(vm, src_uri)
