import sys, os, time, commands, re, logging, signal
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
import kvm_vm, kvm_utils, kvm_subprocess


def preprocess_image(test, params):
    """
    Preprocess a single QEMU image according to the instructions in params.

    @param test: Autotest test object.
    @param params: A dict containing image preprocessing parameters.
    @note: Currently this function just creates an image if requested.
    """
    qemu_img_path = os.path.join(test.bindir, "qemu-img")
    image_dir = os.path.join(test.bindir, "images")
    image_filename = kvm_vm.get_image_filename(params, image_dir)

    create_image = False

    if params.get("force_create_image") == "yes":
        logging.debug("'force_create_image' specified; creating image...")
        create_image = True
    elif params.get("create_image") == "yes" and not \
    os.path.exists(image_filename):
        logging.debug("Creating image...")
        create_image = True

    if create_image:
        if not kvm_vm.create_image(params, qemu_img_path, image_dir):
            message = "Could not create image"
            logging.error(message)
            raise error.TestError(message)


def preprocess_vm(test, params, env, name):
    """
    Preprocess a single VM object according to the instructions in params.
    Start the VM if requested and get a screendump.

    @param test: An Autotest test object.
    @param params: A dict containing VM preprocessing parameters.
    @param env: The environment (a dict-like object).
    @param name: The name of the VM object.
    """
    qemu_path = os.path.join(test.bindir, "qemu")
    image_dir = os.path.join(test.bindir, "images")
    iso_dir = os.path.join(test.bindir, "isos")

    logging.debug("Preprocessing VM '%s'..." % name)
    vm = kvm_utils.env_get_vm(env, name)
    if vm:
        logging.debug("VM object found in environment")
    else:
        logging.debug("VM object does not exist; creating it")
        vm = kvm_vm.VM(name, params, qemu_path, image_dir, iso_dir)
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
                                                            qemu_path,
                                                            image_dir,
                                                            iso_dir):
            logging.debug("VM's qemu command differs from requested one; "
                          "restarting it...")
            start_vm = True

    if start_vm:
        if not vm.create(name, params, qemu_path, image_dir, iso_dir,
                         for_migration):
            message = "Could not start VM"
            logging.error(message)
            raise error.TestError(message)

    scrdump_filename = os.path.join(test.debugdir, "pre_%s.ppm" % name)
    vm.send_monitor_cmd("screendump %s" % scrdump_filename)


def postprocess_image(test, params):
    """
    Postprocess a single QEMU image according to the instructions in params.
    Currently this function just removes an image if requested.

    @param test: An Autotest test object.
    @param params: A dict containing image postprocessing parameters.
    """
    image_dir = os.path.join(test.bindir, "images")

    if params.get("remove_image") == "yes":
        kvm_vm.remove_image(params, image_dir)


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
    qemu_path = os.path.join(test.bindir, "qemu")
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
        mogrify_cmd = ("mogrify -format png %s" %
                       os.path.join(test.debugdir, "*.ppm"))
        kvm_subprocess.run_fg(mogrify_cmd, logging.debug, "(mogrify) ",
                              timeout=30.0)

    # Should we keep the PPM files?
    if params.get("keep_ppm_files") != "yes":
        logging.debug("'keep_ppm_files' not specified; removing all PPM files"
                      " from debug dir...")
        rm_cmd = "rm -vf %s" % os.path.join(test.debugdir, "*.ppm")
        kvm_subprocess.run_fg(rm_cmd, logging.debug, "(rm) ", timeout=5.0)

    # Execute any post_commands
    if params.get("post_command"):
        process_command(test, params, env, params.get("post_command"),
                        int(params.get("post_command_timeout", "600")),
                        params.get("post_command_noncritical") == "yes")


def postprocess_on_error(test, params, env):
    """
    Perform postprocessing operations required only if the test failed.

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    """
    params.update(kvm_utils.get_sub_dict(params, "on_error"))
