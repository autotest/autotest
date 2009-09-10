import sys, os, time, commands, re, logging, signal, glob
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
import kvm_vm, kvm_utils, kvm_subprocess, ppm_utils
try:
    import PIL.Image
except ImportError:
    logging.warning('No python imaging library installed. PPM image '
                    'conversion to JPEG disabled. In order to enable it, '
                    'please install python-imaging or the equivalent for your '
                    'distro.')


def preprocess_image(test, params):
    """
    Preprocess a single QEMU image according to the instructions in params.

    @param test: Autotest test object.
    @param params: A dict containing image preprocessing parameters.
    @note: Currently this function just creates an image if requested.
    """
    image_filename = kvm_vm.get_image_filename(params, test.bindir)

    create_image = False

    if params.get("force_create_image") == "yes":
        logging.debug("'force_create_image' specified; creating image...")
        create_image = True
    elif (params.get("create_image") == "yes" and not
          os.path.exists(image_filename)):
        logging.debug("Creating image...")
        create_image = True

    if create_image and not kvm_vm.create_image(params, test.bindir):
        raise error.TestError("Could not create image")


def preprocess_vm(test, params, env, name):
    """
    Preprocess a single VM object according to the instructions in params.
    Start the VM if requested and get a screendump.

    @param test: An Autotest test object.
    @param params: A dict containing VM preprocessing parameters.
    @param env: The environment (a dict-like object).
    @param name: The name of the VM object.
    """
    logging.debug("Preprocessing VM '%s'..." % name)
    vm = kvm_utils.env_get_vm(env, name)
    if vm:
        logging.debug("VM object found in environment")
    else:
        logging.debug("VM object does not exist; creating it")
        vm = kvm_vm.VM(name, params, test.bindir, env.get("address_cache"))
        kvm_utils.env_register_vm(env, name, vm)

    start_vm = False
    for_migration = False

    if params.get("start_vm_for_migration") == "yes":
        logging.debug("'start_vm_for_migration' specified; (re)starting VM with"
                      " -incoming option...")
        start_vm = True
        for_migration = True
    elif params.get("restart_vm") == "yes":
        logging.debug("'restart_vm' specified; (re)starting VM...")
        start_vm = True
    elif params.get("start_vm") == "yes":
        if not vm.is_alive():
            logging.debug("VM is not alive; starting it...")
            start_vm = True
        elif vm.make_qemu_command() != vm.make_qemu_command(name, params,
                                                            test.bindir):
            logging.debug("VM's qemu command differs from requested one; "
                          "restarting it...")
            start_vm = True

    if start_vm and not vm.create(name, params, test.bindir, for_migration):
        raise error.TestError("Could not start VM")

    scrdump_filename = os.path.join(test.debugdir, "pre_%s.ppm" % name)
    vm.send_monitor_cmd("screendump %s" % scrdump_filename)


def postprocess_image(test, params):
    """
    Postprocess a single QEMU image according to the instructions in params.
    Currently this function just removes an image if requested.

    @param test: An Autotest test object.
    @param params: A dict containing image postprocessing parameters.
    """
    if params.get("remove_image") == "yes":
        kvm_vm.remove_image(params, test.bindir)


def postprocess_vm(test, params, env, name):
    """
    Postprocess a single VM object according to the instructions in params.
    Kill the VM if requested and get a screendump.

    @param test: An Autotest test object.
    @param params: A dict containing VM postprocessing parameters.
    @param env: The environment (a dict-like object).
    @param name: The name of the VM object.
    """
    logging.debug("Postprocessing VM '%s'..." % name)
    vm = kvm_utils.env_get_vm(env, name)
    if vm:
        logging.debug("VM object found in environment")
    else:
        logging.debug("VM object does not exist in environment")
        return

    scrdump_filename = os.path.join(test.debugdir, "post_%s.ppm" % name)
    vm.send_monitor_cmd("screendump %s" % scrdump_filename)

    if params.get("kill_vm") == "yes":
        if not kvm_utils.wait_for(vm.is_dead,
                float(params.get("kill_vm_timeout", 0)), 0.0, 1.0,
                "Waiting for VM to kill itself..."):
            logging.debug("'kill_vm' specified; killing VM...")
        vm.destroy(gracefully = params.get("kill_vm_gracefully") == "yes")


def process_command(test, params, env, command, command_timeout,
                    command_noncritical):
    """
    Pre- or post- custom commands to be executed before/after a test is run

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    @param command: Command to be run.
    @param command_timeout: Timeout for command execution.
    @param command_noncritical: If True test will not fail if command fails.
    """
    # Export environment vars
    for k in params.keys():
        os.putenv("KVM_TEST_%s" % k, str(params[k]))
    # Execute command
    logging.info("Executing command '%s'..." % command)
    (status, output) = kvm_subprocess.run_fg("cd %s; %s" % (test.bindir,
                                                            command),
                                             logging.debug, "(command) ",
                                             timeout=command_timeout)
    if status != 0:
        logging.warn("Custom processing command failed: '%s'" % command)
        if not command_noncritical:
            raise error.TestError("Custom processing command failed")


def process(test, params, env, image_func, vm_func):
    """
    Pre- or post-process VMs and images according to the instructions in params.
    Call image_func for each image listed in params and vm_func for each VM.

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    @param image_func: A function to call for each image.
    @param vm_func: A function to call for each VM.
    """
    # Get list of VMs specified for this test
    vm_names = kvm_utils.get_sub_dict_names(params, "vms")
    for vm_name in vm_names:
        vm_params = kvm_utils.get_sub_dict(params, vm_name)
        # Get list of images specified for this VM
        image_names = kvm_utils.get_sub_dict_names(vm_params, "images")
        for image_name in image_names:
            image_params = kvm_utils.get_sub_dict(vm_params, image_name)
            # Call image_func for each image
            image_func(test, image_params)
        # Call vm_func for each vm
        vm_func(test, vm_params, env, vm_name)


def preprocess(test, params, env):
    """
    Preprocess all VMs and images according to the instructions in params.
    Also, collect some host information, such as the KVM version.

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    """
    # Start tcpdump if it isn't already running
    if not env.has_key("address_cache"):
        env["address_cache"] = {}
    if env.has_key("tcpdump") and not env["tcpdump"].is_alive():
        env["tcpdump"].close()
        del env["tcpdump"]
    if not env.has_key("tcpdump"):
        command = "/usr/sbin/tcpdump -npvi any 'dst port 68'"
        logging.debug("Starting tcpdump (%s)...", command)
        env["tcpdump"] = kvm_subprocess.kvm_tail(
            command=command,
            output_func=_update_address_cache,
            output_params=(env["address_cache"],))
        if kvm_utils.wait_for(lambda: not env["tcpdump"].is_alive(),
                              0.1, 0.1, 1.0):
            logging.warn("Could not start tcpdump")
            logging.warn("Status: %s" % env["tcpdump"].get_status())
            logging.warn("Output:" + kvm_utils.format_str_for_message(
                env["tcpdump"].get_output()))

    # Destroy and remove VMs that are no longer needed in the environment
    requested_vms = kvm_utils.get_sub_dict_names(params, "vms")
    for key in env.keys():
        vm = env[key]
        if not kvm_utils.is_vm(vm):
            continue
        if not vm.name in requested_vms:
            logging.debug("VM '%s' found in environment but not required for"
                          " test; removing it..." % vm.name)
            vm.destroy()
            del env[key]

    # Execute any pre_commands
    if params.get("pre_command"):
        process_command(test, params, env, params.get("pre_command"),
                        int(params.get("pre_command_timeout", "600")),
                        params.get("pre_command_noncritical") == "yes")

    # Preprocess all VMs and images
    process(test, params, env, preprocess_image, preprocess_vm)

    # Get the KVM kernel module version and write it as a keyval
    logging.debug("Fetching KVM module version...")
    if os.path.exists("/dev/kvm"):
        kvm_version = os.uname()[2]
        try:
            file = open("/sys/module/kvm/version", "r")
            kvm_version = file.read().strip()
            file.close()
        except:
            pass
    else:
        kvm_version = "Unknown"
        logging.debug("KVM module not loaded")
    logging.debug("KVM version: %s" % kvm_version)
    test.write_test_keyval({"kvm_version": kvm_version})

    # Get the KVM userspace version and write it as a keyval
    logging.debug("Fetching KVM userspace version...")
    qemu_path = kvm_utils.get_path(test.bindir, params.get("qemu_binary",
                                                           "qemu"))
    version_line = commands.getoutput("%s -help | head -n 1" % qemu_path)
    exp = re.compile("[Vv]ersion .*?,")
    match = exp.search(version_line)
    if match:
        kvm_userspace_version = " ".join(match.group().split()[1:]).strip(",")
    else:
        kvm_userspace_version = "Unknown"
        logging.debug("Could not fetch KVM userspace version")
    logging.debug("KVM userspace version: %s" % kvm_userspace_version)
    test.write_test_keyval({"kvm_userspace_version": kvm_userspace_version})


def postprocess(test, params, env):
    """
    Postprocess all VMs and images according to the instructions in params.

    @param test: An Autotest test object.
    @param params: Dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    """
    process(test, params, env, postprocess_image, postprocess_vm)

    # Should we convert PPM files to PNG format?
    if params.get("convert_ppm_files_to_png") == "yes":
        logging.debug("'convert_ppm_files_to_png' specified; converting PPM"
                      " files to PNG format...")
        try:
            for f in glob.glob(os.path.join(test.debugdir, "*.ppm")):
                if ppm_utils.image_verify_ppm_file(f):
                    new_path = f.replace(".ppm", ".png")
                    image = PIL.Image.open(f)
                    image.save(new_path, format='PNG')
        except NameError:
            pass

    # Should we keep the PPM files?
    if params.get("keep_ppm_files") != "yes":
        logging.debug("'keep_ppm_files' not specified; removing all PPM files"
                      " from debug dir...")
        for f in glob.glob(os.path.join(test.debugdir, '*.ppm')):
            os.unlink(f)

    # Execute any post_commands
    if params.get("post_command"):
        process_command(test, params, env, params.get("post_command"),
                        int(params.get("post_command_timeout", "600")),
                        params.get("post_command_noncritical") == "yes")

    # Kill the tailing threads of all VMs
    for vm in kvm_utils.env_get_all_vms(env):
        vm.kill_tail_thread()

    # Terminate tcpdump if no VMs are alive
    living_vms = [vm for vm in kvm_utils.env_get_all_vms(env) if vm.is_alive()]
    if not living_vms and env.has_key("tcpdump"):
        env["tcpdump"].close()
        del env["tcpdump"]


def postprocess_on_error(test, params, env):
    """
    Perform postprocessing operations required only if the test failed.

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    """
    params.update(kvm_utils.get_sub_dict(params, "on_error"))


def _update_address_cache(address_cache, line):
    if re.search("Your.IP", line, re.IGNORECASE):
        matches = re.findall(r"\d*\.\d*\.\d*\.\d*", line)
        if matches:
            address_cache["last_seen"] = matches[0]
    if re.search("Client.Ethernet.Address", line, re.IGNORECASE):
        matches = re.findall(r"\w*:\w*:\w*:\w*:\w*:\w*", line)
        if matches and address_cache.get("last_seen"):
            mac_address = matches[0].lower()
            logging.debug("(address cache) Adding cache entry: %s ---> %s",
                          mac_address, address_cache.get("last_seen"))
            address_cache[mac_address] = address_cache.get("last_seen")
            del address_cache["last_seen"]
