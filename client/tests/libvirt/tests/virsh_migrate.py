import logging, os, re, time, shutil, codecs, tempfile
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import libvirt_vm, virt_utils, virt_test_utils

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
        try:
            if libvirt_vm.virsh_domain_exists(vm.name, vm.connect_uri):
                vm_state = vm.state()
                if vm_state == "paused":
                    vm.resume()
                elif vm_state == "shut off":
                    vm.start()
                vm.destroy()

                if vm.is_persistent():
                    vm.undefine()

        except Exception, detail:
            logging.error("Cleaning up destination failed.\n%s" % detail)

        finally:
            if src_uri != "":
                vm.connect_uri = src_uri

    # vm.migrate() did some error checking, so when we want to test 
    # some incorrect options, we have to construct our own command.
    def do_error_migration(vm_ref, dest_uri, options = "", extra = "", uri = ""):
        cmd = ""
        if uri == "":
            cmd += "virsh migrate "
        else:
            cmd += "virsh -c %s migrate " % uri
        cmd += options
        if vm_ref != "":
            cmd += " --domain %s " % vm_ref
        if dest_uri != "":
            cmd += " --desturi %s " % dest_uri
        cmd += extra

        cmd_result = utils.run(cmd, ignore_status = True)
        logging.info("Output: %s", cmd_result.stdout.strip())
        logging.error("Error: %s", cmd_result.stderr.strip())
        logging.info("Status: %d", cmd_result.exit_status)
        # Here we should keep the return value type the same as do_migration().
        if cmd_result.exit_status == 0:
            return True
        else:
            return False

    def do_migration(delay, vm, dest_uri, options, extra):
        logging.info("Sleeping %d seconds before migration" % delay)
        time.sleep(delay)
        # Migrate the guest.
        successful = vm.migrate(dest_uri, options, extra)
        if not successful:
            logging.error("Migration failed for %s." % vm_name)
            return False

        if vm.is_alive(): # vm.connect_uri was updated
            logging.info("Alive guest found on destination %s." % dest_uri)
        else:
            logging.error("VM not alive on destination %s" % dest_uri)
            return False

        # FIXME: This needs to be tested, but won't work currently
        # vm.verify_kernel_crash()
        logging.info("vm.verify_kernel_crash() needs to be tested, \
                      but won't work currently.")
        return True

    vm_name = params.get("main_vm")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    # For safety reasons, we'd better back up  xmlfile.
    vm_xmlfile = "/etc/libvirt/qemu/%s.xml" % vm_name
    vm_xmlfile_bak = tempfile.mktemp(dir = "/tmp")
    if os.path.exists(vm_xmlfile_bak):
        os.remove(vm_xmlfile_bak)
    shutil.copyfile(vm_xmlfile, vm_xmlfile_bak)
    if not os.path.exists(vm_xmlfile_bak):
        logging.warning(warning_text % "Backing up xmlfile failed.")

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
    delay = int(params.get("virsh_migrate_delay", 10))
    status_error = params.get("status_error", 'no')
    libvirtd_state = params.get("virsh_migrate_libvirtd_state", 'on')
    src_state = params.get("virsh_migrate_src_state", "running")
    new_nic_mac = ""
    dest_xmlfile = ""

    exception = False
    try:
        # Confirm VM can be accessed through network.
        virt_utils.wait_for(None, delay, first=delay, step=1.0, text=None)
        vm_ip = vm.get_address()
        s_ping, o_ping = virt_test_utils.ping(vm_ip, count = 2, timeout = delay)
        logging.info(o_ping)
        if s_ping != 0:
            raise error.TestError("%s did not respond after %d sec." % (vm.name, delay))

        # Prepare for --xml.
        if options.count("xml") or extra.count("xml"):
            new_nic_mac = virt_utils.generate_mac_address(vm, 1)
            logging.info("New mac address: %s" % new_nic_mac)
            dest_xmlfile = params.get("virsh_migrate_xml", "")
            if dest_xmlfile != "":
                ret_attach = vm.attach_interface("bridge", "--source virbr0 --mac %s" % new_nic_mac)
                if not ret_attach:
                    exception = True
                    raise error.TestError("Attaching nic to %s failed." % vm.name)
                vm_xml_new = vm.get_xml()
                logging.info("Xml file on source: %s" % vm_xml_new)
                f = codecs.open(dest_xmlfile, 'wb', encoding='utf-8')
                f.write(vm_xml_new)
                f.close()
                if not os.path.exists(dest_xmlfile):
                    exception = True
                    raise erro.TestError("Creating %s failed." % dest_xmlfile)

        # Turn VM into certain state.
        if src_state == "paused":
            if vm.is_alive():
                vm.pause()
        elif src_state == "shut off":
            if vm.is_alive():
                if not vm.shutdown():
                    vm.destroy()

        # Turn libvirtd into certain state.
        if libvirtd_state == "off":
            libvirt_vm.libvirtd_stop()

        # Test uni-direction migration.
        if status_error == 'no':
            ret_migrate = do_migration(delay, vm, dest_uri, options, extra)
        else:
            vm_ref = params.get("vm_ref", vm.name)
            dest_uri_ref = params.get("dest_uri_ref", dest_uri)
            ret_migrate = do_error_migration(vm_ref, dest_uri_ref, options, extra)

        # Recover libvirtd state.
        if libvirtd_state == "off":
            libvirt_vm.libvirtd_start()

        # Recover VM state.
        if src_state == "paused":
            vm.resume()
        elif src_state == "shut off":
            vm.start()

        # Check vm state on destination.
        check_dest_state = True
        dest_state = params.get("virsh_migrate_dest_state", "running")
        check_dest_state = check_vm_state(vm, dest_state)
        logging.info("Supposed state: %s\nActual state: %s" % (dest_state, vm.state()))

        # Checking for --persistent.
        check_dest_persistent = True
        if options.count("persistent") or extra.count("persistent"):
            if not vm.is_persistent():
                check_dest_persistent = False

        # Checking for --undefinesource.
        check_src_undefine = True
        if options.count("undefinesource") or extra.count("undefinesource"):
            if libvirt_vm.virsh_domain_exists(vm_name, src_uri):
                check_src_undefine = False

        # Checking for --dname.
        check_dest_dname = True
        if options.count("dname") or extra.count("dname"):
            dname = params.get("virsh_migrate_dname")
            if not libvirt_vm.virsh_domain_exists(dname, dest_uri):
                check_dest_dname = False

        # Checking for --xml.
        check_dest_xml = True
        if options.count("xml") or extra.count("xml"):
            if dest_xmlfile != "":
                vm_dest_xml = vm.get_xml()
                logging.info("Xml file on destination: %s" % vm_dest_xml)
                if not re.search(new_nic_mac, vm_dest_xml):
                    check_dest_xml = False

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
            do_migration(delay, vm, back_dest_uri, back_options, back_extra)

    except Exception, detail:
        # Whatever error occurs, we have to clean up all environment.
        exception = True
        logging.error("Error occurred.\n%s" % detail)

    finally:
        # Cleanup destination.
        # Make sure vm.connect_uri is the destination uri.
        vm.connect_uri = dest_uri
        if options.count("dname") or extra.count("dname"):
            # Use the VM object to remove 
            vm.name = params.get("virsh_migrate_dname")
            cleanup_dest(vm, "")
            vm.name = vm_name
        cleanup_dest(vm, src_uri)

        # Recover source (just in case).
        # vm.connect_uri has been set back to src_uri in cleanup_dest().
        if not libvirt_vm.virsh_domain_exists(vm_name, src_uri):
            vm.define(vm_xmlfile_bak)
        else:
            if not vm.shutdown():
                vm.destroy()

        # Cleanup source.
        if os.path.exists(vm_xmlfile_bak):
            os.remove(vm_xmlfile_bak)
        if os.path.exists(dest_xmlfile):
            os.remove(dest_xmlfile)

        if exception:
            raise error.TestError("Error occurred. \n%s" % detail)

        # Check test result.
        if status_error == 'yes':
            if ret_migrate:
                raise error.TestFail("Migration finished with unexpected status.")
        else:
            if not ret_migrate:
                raise error.TestFail("Migration finished with unexpected status.")
            if not check_dest_state:
                raise error.TestFail("Wrong VM state on destination.")
            if not check_dest_persistent:
                raise error.TestFail("VM is not persistent on destination.")
            if not check_src_undefine:
                raise error.TestFail("VM is not undefined on source.")
            if not check_dest_dname:
                raise error.TestFail("Wrong VM name %s on destination." % dname)
            if not check_dest_xml:
                raise error.TestFail("Wrong xml configuration on destination.")

