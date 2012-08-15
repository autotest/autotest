import os, time, commands, re, logging, glob, threading, shutil
from autotest.client import utils
from autotest.client.shared import error
import aexpect, kvm_monitor, ppm_utils, virt_test_setup, virt_vm, kvm_vm
import libvirt_vm, virt_video_maker, virt_utils, virt_storage, kvm_storage
import virt_remote, virt_v2v, ovirt

try:
    import PIL.Image
except ImportError:
    logging.warning('No python imaging library installed. PPM image '
                    'conversion to JPEG disabled. In order to enable it, '
                    'please install python-imaging or the equivalent for your '
                    'distro.')

_screendump_thread = None
_screendump_thread_termination_event = None


def preprocess_image(test, params, image_name):
    """
    Preprocess a single QEMU image according to the instructions in params.

    @param test: Autotest test object.
    @param params: A dict containing image preprocessing parameters.
    @note: Currently this function just creates an image if requested.
    """
    if params.get("storage_type") == "iscsi":
        iscsidev = kvm_storage.Iscsidev(params, test.bindir, image_name)
        params["image_name"] = iscsidev.setup()
    else:
        image_filename = virt_storage.get_image_filename(params, test.bindir)

        create_image = False

        if params.get("force_create_image") == "yes":
            logging.debug("Param 'force_create_image' specified, creating image")
            create_image = True
        elif (params.get("create_image") == "yes" and not
              os.path.exists(image_filename)):
            create_image = True

        if create_image:
            image = kvm_storage.QemuImg(params, test.bindir, image_name)
            if not image.create(params):
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
    logging.debug("Preprocessing VM '%s'", name)
    vm = env.get_vm(name)
    vm_type = params.get('vm_type')
    target = params.get('target')
    if not vm:
        logging.debug("VM object for '%s' does not exist, creating it", name)
        if vm_type == 'kvm':
            vm = kvm_vm.VM(name, params, test.bindir, env.get("address_cache"))
        if vm_type == 'libvirt':
            vm = libvirt_vm.VM(name, params, test.bindir, env.get("address_cache"))
        if vm_type == 'virt_v2v':
            if target == 'libvirt' or target is None:
                vm = libvirt_vm.VM(name, params, test.bindir, env.get("address_cache"))
            if target == 'ovirt':
                vm = ovirt.VMManager(name, params, test.bindir, env.get("address_cache"))
        env.register_vm(name, vm)

    remove_vm = False
    if params.get("force_remove_vm") == "yes":
        logging.debug("'force_remove_vm' specified; removing VM...")
        remove_vm = True

    if remove_vm:
        vm.remove()

    start_vm = False

    if params.get("restart_vm") == "yes":
        logging.debug("Param 'restart_vm' specified, (re)starting VM")
        start_vm = True
    elif params.get("migration_mode"):
        logging.debug("Param 'migration_mode' specified, starting VM in "
                      "incoming migration mode")
        start_vm = True
    elif params.get("start_vm") == "yes":
        # need to deal with libvirt VM differently than qemu
        if vm_type == 'libvirt' or vm_type == 'virt_v2v':
            if not vm.is_alive():
                logging.debug("VM is not alive; starting it...")
                start_vm = True
        else:
            if not vm.is_alive():
                logging.debug("VM is not alive, starting it")
                start_vm = True
            if vm.needs_restart(name=name, params=params, basedir=test.bindir):
                logging.debug("Current VM specs differ from requested one; "
                              "restarting it")
                start_vm = True

    if start_vm:
        if vm_type == "libvirt" and params.get("type") != "unattended_install":
            vm.params = params
            vm.start()
        elif vm_type == "virt_v2v":
            vm.params = params
            vm.start()
        else:
            # Start the VM (or restart it if it's already up)
            vm.create(name, params, test.bindir,
                      migration_mode=params.get("migration_mode"),
                      migration_fd=params.get("migration_fd"))
            if params.get("paused_after_start_vm") == "yes":
                if vm.state() != "paused":
                    vm.pause()
    else:
        # Don't start the VM, just update its params
        vm.params = params


def postprocess_image(test, params, image_name):
    """
    Postprocess a single QEMU image according to the instructions in params.

    @param test: An Autotest test object.
    @param params: A dict containing image postprocessing parameters.
    """
    if params.get("storage_type") == "iscsi":
        iscsidev = kvm_storage.Iscsidev(params, test.bindir, image_name)
        iscsidev.cleanup()
    else:
        image = kvm_storage.QemuImg(params, test.bindir, image_name)
        if params.get("check_image") == "yes":
            try:
                image.check_image(params, test.bindir)
            except Exception, e:
                if params.get("restore_image_on_check_error", "no") == "yes":
                    image.backup_image(params, test.bindir, "restore", True)
                raise e
        if params.get("remove_image") == "yes":
            image.remove()


def postprocess_vm(test, params, env, name):
    """
    Postprocess a single VM object according to the instructions in params.
    Kill the VM if requested and get a screendump.

    @param test: An Autotest test object.
    @param params: A dict containing VM postprocessing parameters.
    @param env: The environment (a dict-like object).
    @param name: The name of the VM object.
    """
    logging.debug("Postprocessing VM '%s'" % name)
    vm = env.get_vm(name)
    if not vm:
        return

    # Encode an HTML 5 compatible video from the screenshots produced?
    screendump_dir = os.path.join(test.debugdir, "screendumps_%s" % vm.name)
    if (params.get("encode_video_files", "yes") == "yes" and
        glob.glob("%s/*" % screendump_dir)):
        logging.debug("Param 'encode_video_files' specified, trying to "
                      "encode a video from the screenshots produced by "
                      "vm %s", vm.name)
        try:
            video = virt_video_maker.GstPythonVideoMaker()
            if (video.has_element('vp8enc') and video.has_element('webmmux')):
                video_file = os.path.join(test.debugdir, "%s-%s.webm" %
                                          (vm.name, test.iteration))
            else:
                video_file = os.path.join(test.debugdir, "%s-%s.ogg" %
                                          (vm.name, test.iteration))
            video.start(screendump_dir, video_file)

        except Exception, detail:
            logging.info("Param 'encode_video_files' specified, but video "
                         "creation failed for vm %s: %s", vm.name, detail)

    if params.get("kill_vm") == "yes":
        kill_vm_timeout = float(params.get("kill_vm_timeout", 0))
        if kill_vm_timeout:
            logging.debug("Param 'kill_vm' specified, waiting for VM to shut "
                          "down before killing it")
            virt_utils.wait_for(vm.is_dead, kill_vm_timeout, 0, 1)
        else:
            logging.debug("Param 'kill_vm' specified, killing VM")
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
    for k in params:
        os.putenv("KVM_TEST_%s" % k, str(params[k]))
    # Execute commands
    try:
        utils.system("cd %s; %s" % (test.bindir, command))
    except error.CmdError, e:
        if command_noncritical:
            logging.warn(e)
        else:
            raise


def process(test, params, env, image_func, vm_func, vm_first=False):
    """
    Pre- or post-process VMs and images according to the instructions in params.
    Call image_func for each image listed in params and vm_func for each VM.

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    @param image_func: A function to call for each image.
    @param vm_func: A function to call for each VM.
    @param vm_first: Call vm_func first or not.
    """
    def _call_vm_func():
        for vm_name in params.objects("vms"):
            vm_params = params.object_params(vm_name)
            vm = env.get_vm(vm_name)
            vm_func(test, vm_params, env, vm_name)

    def _call_image_func():
        if params.objects("vms"):
            for vm_name in params.objects("vms"):
                vm_params = params.object_params(vm_name)
                vm = env.get_vm(vm_name)
                for image_name in vm_params.objects("images"):
                    image_params = vm_params.object_params(image_name)
                    # Call image_func for each image
                    if vm is not None and vm.is_alive():
                        vm.pause()
                    try:
                        image_func(test, image_params, image_name)
                    finally:
                        if vm is not None and vm.is_alive():
                            vm.resume()
        else:
            for image_name in params.objects("images"):
                image_params = params.object_params(image_name)
                image_func(test, image_params, image_name)

    if not vm_first:
        _call_image_func()

    _call_vm_func()

    if vm_first:
        _call_image_func()


@error.context_aware
def preprocess(test, params, env):
    """
    Preprocess all VMs and images according to the instructions in params.
    Also, collect some host information, such as the KVM version.

    @param test: An Autotest test object.
    @param params: A dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    """
    error.context("preprocessing")
    port = params.get('shell_port')
    prompt = params.get('shell_prompt')
    address = params.get('ovirt_node_address')
    username = params.get('ovirt_node_user')
    password = params.get('ovirt_node_password')

    # Start tcpdump if it isn't already running
    if "address_cache" not in env:
        env["address_cache"] = {}
    if "tcpdump" in env and not env["tcpdump"].is_alive():
        env["tcpdump"].close()
        del env["tcpdump"]
    if "tcpdump" not in env and params.get("run_tcpdump", "yes") == "yes":
        cmd = "%s -npvi any 'dst port 68'" % virt_utils.find_command("tcpdump")
        if params.get("remote_preprocess") == "yes":
            logging.debug("Starting tcpdump '%s' on remote host", cmd)
            login_cmd = ("ssh -o UserKnownHostsFile=/dev/null -o \
                         PreferredAuthentications=password -p %s %s@%s" %
                         (port, username, address))
            env["tcpdump"] = aexpect.ShellSession(
                login_cmd,
                output_func=_update_address_cache,
                output_params=(env["address_cache"],))
            virt_remote._remote_login(env["tcpdump"], username, password, prompt)
            env["tcpdump"].sendline(cmd)
        else:
            logging.debug("Starting tcpdump '%s' on local host", cmd)
            env["tcpdump"] = aexpect.Tail(
                command=cmd,
                output_func=_update_address_cache,
                output_params=(env["address_cache"],))

        if virt_utils.wait_for(lambda: not env["tcpdump"].is_alive(),
                              0.1, 0.1, 1.0):
            logging.warn("Could not start tcpdump")
            logging.warn("Status: %s" % env["tcpdump"].get_status())
            logging.warn("Output:" + virt_utils.format_str_for_message(
                env["tcpdump"].get_output()))

    # Destroy and remove VMs that are no longer needed in the environment
    requested_vms = params.objects("vms")
    for key in env.keys():
        vm = env[key]
        if not virt_utils.is_vm(vm):
            continue
        if not vm.name in requested_vms:
            logging.debug("VM '%s' found in environment but not required for "
                          "test, destroying it" % vm.name)
            vm.destroy()
            del env[key]

    # Get Host cpu type
    if params.get("auto_cpu_model") == "yes":
        if not env.get("cpu_model"):
            env["cpu_model"] = virt_utils.get_cpu_model()
        params["cpu_model"] = env.get("cpu_model")

    kvm_ver_cmd = params.get("kvm_ver_cmd", "")

    if kvm_ver_cmd:
        try:
            cmd_result = utils.run(kvm_ver_cmd)
            kvm_version = cmd_result.stdout.strip()
        except error.CmdError, e:
            kvm_version = "Unknown"
    else:
        # Get the KVM kernel module version and write it as a keyval
        if os.path.exists("/dev/kvm"):
            try:
                kvm_version = open("/sys/module/kvm/version").read().strip()
            except Exception:
                kvm_version = os.uname()[2]
        else:
            logging.warning("KVM module not loaded")
            kvm_version = "Unknown"

    logging.debug("KVM version: %s" % kvm_version)
    test.write_test_keyval({"kvm_version": kvm_version})

    # Get the KVM userspace version and write it as a keyval
    kvm_userspace_ver_cmd = params.get("kvm_userspace_ver_cmd", "")

    if kvm_userspace_ver_cmd:
        try:
            cmd_result = utils.run(kvm_userspace_ver_cmd)
            kvm_userspace_version = cmd_result.stdout.strip()
        except error.CmdError, e:
            kvm_userspace_version = "Unknown"
    else:
        qemu_path = virt_utils.get_path(test.bindir,
                                        params.get("qemu_binary", "qemu"))
        version_line = commands.getoutput("%s -help | head -n 1" % qemu_path)
        matches = re.findall("[Vv]ersion .*?,", version_line)
        if matches:
            kvm_userspace_version = " ".join(matches[0].split()[1:]).strip(",")
        else:
            kvm_userspace_version = "Unknown"

    logging.debug("KVM userspace version: %s" % kvm_userspace_version)
    test.write_test_keyval({"kvm_userspace_version": kvm_userspace_version})

    if params.get("setup_hugepages") == "yes":
        h = virt_test_setup.HugePageConfig(params)
        h.setup()
        if params.get("vm_type") == "libvirt":
            libvirt_vm.libvirtd_restart()

    if params.get("setup_thp") == "yes":
        thp = virt_test_setup.TransparentHugePageConfig(test, params)
        thp.setup()

    # Execute any pre_commands
    if params.get("pre_command"):
        process_command(test, params, env, params.get("pre_command"),
                        int(params.get("pre_command_timeout", "600")),
                        params.get("pre_command_noncritical") == "yes")

    #Clone master image from vms.
    if params.get("master_images_clone"):
        for vm_name in params.get("vms").split():
            vm = env.get_vm(vm_name)
            if vm:
                vm.destroy(free_mac_addresses=False)
                env.unregister_vm(vm_name)

            vm_params = params.object_params(vm_name)
            for image in vm_params.get("master_images_clone").split():
                image_obj = kvm_storage.QemuImg(params, test.bindir, image)
                image_obj.clone_image(params, vm_name, image, test.bindir)

    # Preprocess all VMs and images
    if params.get("not_preprocess","no") == "no":
        process(test, params, env, preprocess_image, preprocess_vm)

    # Start the screendump thread
    if params.get("take_regular_screendumps") == "yes":
        logging.debug("Starting screendump thread")
        global _screendump_thread, _screendump_thread_termination_event
        _screendump_thread_termination_event = threading.Event()
        _screendump_thread = threading.Thread(target=_take_screendumps,
                                              args=(test, params, env))
        _screendump_thread.start()


@error.context_aware
def postprocess(test, params, env):
    """
    Postprocess all VMs and images according to the instructions in params.

    @param test: An Autotest test object.
    @param params: Dict containing all VM and image parameters.
    @param env: The environment (a dict-like object).
    """
    error.context("postprocessing")

    # Postprocess all VMs and images
    process(test, params, env, postprocess_image, postprocess_vm, vm_first=True)

    # Terminate the screendump thread
    global _screendump_thread, _screendump_thread_termination_event
    if _screendump_thread is not None:
        logging.debug("Terminating screendump thread")
        _screendump_thread_termination_event.set()
        _screendump_thread.join(10)
        _screendump_thread = None

    # Warn about corrupt PPM files
    for f in glob.glob(os.path.join(test.debugdir, "*.ppm")):
        if not ppm_utils.image_verify_ppm_file(f):
            logging.warn("Found corrupt PPM file: %s", f)

    # Should we convert PPM files to PNG format?
    if params.get("convert_ppm_files_to_png") == "yes":
        logging.debug("Param 'convert_ppm_files_to_png' specified, converting "
                      "PPM files to PNG format")
        try:
            for f in glob.glob(os.path.join(test.debugdir, "*.ppm")):
                if ppm_utils.image_verify_ppm_file(f):
                    new_path = f.replace(".ppm", ".png")
                    image = PIL.Image.open(f)
                    image.save(new_path, format='PNG')
        except NameError:
            pass

    # Should we keep the PPM files?
    if params.get("keep_ppm_files", "no") != "yes":
        logging.debug("Param 'keep_ppm_files' not specified, removing all PPM "
                      "files from debug dir")
        for f in glob.glob(os.path.join(test.debugdir, '*.ppm')):
            os.unlink(f)

    # Should we keep the screendump dirs?
    if params.get("keep_screendumps", "no") != "yes":
        logging.debug("Param 'keep_screendumps' not specified, removing "
                      "screendump dirs")
        for d in glob.glob(os.path.join(test.debugdir, "screendumps_*")):
            if os.path.isdir(d) and not os.path.islink(d):
                shutil.rmtree(d, ignore_errors=True)

    # Should we keep the video files?
    if params.get("keep_video_files", "yes") != "yes":
        logging.debug("Param 'keep_video_files' not specified, removing all .ogg "
                      "and .webm files from debug dir")
        for f in (glob.glob(os.path.join(test.debugdir, '*.ogg')) +
                  glob.glob(os.path.join(test.debugdir, '*.webm'))):
            os.unlink(f)

    # Kill all unresponsive VMs
    if params.get("kill_unresponsive_vms") == "yes":
        logging.debug("Param 'kill_unresponsive_vms' specified, killing all "
                      "VMs that fail to respond to a remote login request")
        for vm in env.get_all_vms():
            if vm.is_alive():
                try:
                    session = vm.login()
                    session.close()
                except (virt_remote.LoginError, virt_vm.VMError), e:
                    logging.warn(e)
                    vm.destroy(gracefully=False)

    # Kill all aexpect tail threads
    aexpect.kill_tail_threads()

    # Terminate tcpdump if no VMs are alive
    living_vms = [vm for vm in env.get_all_vms() if vm.is_alive()]
    if not living_vms and "tcpdump" in env:
        env["tcpdump"].close()
        del env["tcpdump"]

    if params.get("setup_hugepages") == "yes":
        h = virt_test_setup.HugePageConfig(params)
        h.cleanup()
        if params.get("vm_type") == "libvirt":
            libvirt_vm.libvirtd_restart()

    if params.get("setup_thp") == "yes":
        thp = virt_test_setup.TransparentHugePageConfig(test, params)
        thp.cleanup()

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
    params.update(params.object_params("on_error"))


def _update_address_cache(address_cache, line):
    if re.search("Your.IP", line, re.IGNORECASE):
        matches = re.findall(r"\d*\.\d*\.\d*\.\d*", line)
        if matches:
            address_cache["last_seen"] = matches[0]
    if re.search("Client.Ethernet.Address", line, re.IGNORECASE):
        matches = re.findall(r"\w*:\w*:\w*:\w*:\w*:\w*", line)
        if matches and address_cache.get("last_seen"):
            mac_address = matches[0].lower()
            if time.time() - address_cache.get("time_%s" % mac_address, 0) > 5:
                logging.debug("(address cache) DHCP lease OK: %s --> %s",
                              mac_address, address_cache.get("last_seen"))
            address_cache[mac_address] = address_cache.get("last_seen")
            address_cache["time_%s" % mac_address] = time.time()
            del address_cache["last_seen"]


def _take_screendumps(test, params, env):
    global _screendump_thread_termination_event
    temp_dir = test.debugdir
    if params.get("screendump_temp_dir"):
        temp_dir = virt_utils.get_path(test.bindir,
                                      params.get("screendump_temp_dir"))
        try:
            os.makedirs(temp_dir)
        except OSError:
            pass
    temp_filename = os.path.join(temp_dir, "scrdump-%s.ppm" %
                                 virt_utils.generate_random_string(6))
    delay = float(params.get("screendump_delay", 5))
    quality = int(params.get("screendump_quality", 30))

    cache = {}
    counter = {}

    while True:
        for vm in env.get_all_vms():
            if vm not in counter.keys():
                counter[vm] = 0
            if not vm.is_alive():
                continue
            try:
                vm.screendump(filename=temp_filename, debug=False)
            except kvm_monitor.MonitorError, e:
                logging.warn(e)
                continue
            except AttributeError, e:
                logging.warn(e)
                continue
            if not os.path.exists(temp_filename):
                logging.warn("VM '%s' failed to produce a screendump", vm.name)
                continue
            if not ppm_utils.image_verify_ppm_file(temp_filename):
                logging.warn("VM '%s' produced an invalid screendump", vm.name)
                os.unlink(temp_filename)
                continue
            screendump_dir = os.path.join(test.debugdir,
                                          "screendumps_%s" % vm.name)
            try:
                os.makedirs(screendump_dir)
            except OSError:
                pass
            counter[vm] += 1
            screendump_filename = os.path.join(screendump_dir, "%04d.jpg" %
                                               counter[vm])
            hash = utils.hash_file(temp_filename)
            if hash in cache:
                try:
                    os.link(cache[hash], screendump_filename)
                except OSError:
                    pass
            else:
                try:
                    try:
                        image = PIL.Image.open(temp_filename)
                        image.save(screendump_filename, format="JPEG",
                                   quality=quality)
                        cache[hash] = screendump_filename
                    except IOError, error_detail:
                        logging.warning("VM '%s' failed to produce a "
                                        "screendump: %s", vm.name, error_detail)
                        # Decrement the counter as we in fact failed to
                        # produce a converted screendump
                        counter[vm] -= 1
                except NameError:
                    pass
            os.unlink(temp_filename)

        if _screendump_thread_termination_event is not None:
            if _screendump_thread_termination_event.isSet():
                _screendump_thread_termination_event = None
                break
            _screendump_thread_termination_event.wait(delay)
