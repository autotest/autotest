import re, os, logging, commands
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import virt_vm, virt_utils, virt_env_process


def run_qemu_img(test, params, env):
    """
    'qemu-img' functions test:
    1) Judge what subcommand is going to be tested
    2) Run subcommand test

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    cmd = virt_utils.get_path(test.bindir, params.get("qemu_img_binary"))
    if not os.path.exists(cmd):
        raise error.TestError("Binary of 'qemu-img' not found")
    image_format = params.get("image_format")
    image_size = params.get("image_size", "10G")
    image_name = virt_vm.get_image_filename(params, test.bindir)


    def _check(cmd, img):
        """
        Simple 'qemu-img check' function implementation.

        @param cmd: qemu-img base command.
        @param img: image to be checked
        """
        cmd += " check %s" % img
        logging.info("Checking image '%s'...", img)
        try:
            output = utils.system_output(cmd)
        except error.CmdError, e:
            if "does not support checks" in str(e):
                return (True, "")
            else:
                return (False, str(e))
        return (True, output)


    def check_test(cmd):
        """
        Subcommand 'qemu-img check' test.

        This tests will 'dd' to create a specified size file, and check it.
        Then convert it to supported image_format in each loop and check again.

        @param cmd: qemu-img base command.
        """
        test_image = virt_utils.get_path(test.bindir,
                                        params.get("image_name_dd"))
        print "test_image = %s" % test_image
        create_image_cmd = params.get("create_image_cmd")
        create_image_cmd = create_image_cmd % test_image
        print "create_image_cmd = %s" % create_image_cmd
        utils.system(create_image_cmd)
        s, o = _check(cmd, test_image)
        if not s:
            raise error.TestFail("Check image '%s' failed with error: %s" %
                                                           (test_image, o))
        for fmt in params.get("supported_image_formats").split():
            output_image = test_image + ".%s" % fmt
            _convert(cmd, fmt, test_image, output_image)
            s, o = _check(cmd, output_image)
            if not s:
                raise error.TestFail("Check image '%s' got error: %s" %
                                                     (output_image, o))
            os.remove(output_image)
        os.remove(test_image)


    def _create(cmd, img_name, fmt, img_size=None, base_img=None,
               base_img_fmt=None, encrypted="no"):
        """
        Simple wrapper of 'qemu-img create'

        @param cmd: qemu-img base command.
        @param img_name: name of the image file
        @param fmt: image format
        @param img_size:  image size
        @param base_img: base image if create a snapshot image
        @param base_img_fmt: base image format if create a snapshot image
        @param encrypted: indicates whether the created image is encrypted
        """
        cmd += " create"
        if encrypted == "yes":
            cmd += " -e"
        if base_img:
            cmd += " -b %s" % base_img
            if base_img_fmt:
                cmd += " -F %s" % base_img_fmt
        cmd += " -f %s" % fmt
        cmd += " %s" % img_name
        if img_size:
            cmd += " %s" % img_size
        utils.system(cmd)


    def create_test(cmd):
        """
        Subcommand 'qemu-img create' test.

        @param cmd: qemu-img base command.
        """
        image_large = params.get("image_name_large")
        img = virt_utils.get_path(test.bindir, image_large)
        img += '.' + image_format
        _create(cmd, img_name=img, fmt=image_format,
               img_size=params.get("image_size_large"))
        os.remove(img)


    def _convert(cmd, output_fmt, img_name, output_filename,
                fmt=None, compressed="no", encrypted="no"):
        """
        Simple wrapper of 'qemu-img convert' function.

        @param cmd: qemu-img base command.
        @param output_fmt: the output format of converted image
        @param img_name: image name that to be converted
        @param output_filename: output image name that converted
        @param fmt: output image format
        @param compressed: whether output image is compressed
        @param encrypted: whether output image is encrypted
        """
        cmd += " convert"
        if compressed == "yes":
            cmd += " -c"
        if encrypted == "yes":
            cmd += " -e"
        if fmt:
            cmd += " -f %s" % fmt
        cmd += " -O %s" % output_fmt
        cmd += " %s %s" % (img_name, output_filename)
        logging.info("Converting '%s' from format '%s' to '%s'", img_name, fmt,
                     output_fmt)
        utils.system(cmd)


    def convert_test(cmd):
        """
        Subcommand 'qemu-img convert' test.

        @param cmd: qemu-img base command.
        """
        dest_img_fmt = params.get("dest_image_format")
        output_filename = "%s.converted_%s" % (image_name, dest_img_fmt)

        _convert(cmd, dest_img_fmt, image_name, output_filename,
                image_format, params.get("compressed"), params.get("encrypted"))

        if dest_img_fmt == "qcow2":
            s, o = _check(cmd, output_filename)
            if s:
                os.remove(output_filename)
            else:
                raise error.TestFail("Check image '%s' failed with error: %s" %
                                                        (output_filename, o))
        else:
            os.remove(output_filename)


    def _info(cmd, img, sub_info=None, fmt=None):
        """
        Simple wrapper of 'qemu-img info'.

        @param cmd: qemu-img base command.
        @param img: image file
        @param sub_info: sub info, say 'backing file'
        @param fmt: image format
        """
        cmd += " info"
        if fmt:
            cmd += " -f %s" % fmt
        cmd += " %s" % img

        try:
            output = utils.system_output(cmd)
        except error.CmdError, e:
            logging.error("Get info of image '%s' failed: %s", img, str(e))
            return None

        if not sub_info:
            return output

        sub_info += ": (.*)"
        matches = re.findall(sub_info, output)
        if matches:
            return matches[0]
        return None


    def info_test(cmd):
        """
        Subcommand 'qemu-img info' test.

        @param cmd: qemu-img base command.
        """
        img_info = _info(cmd, image_name)
        logging.info("Info of image '%s':\n%s", image_name, img_info)
        if not image_format in img_info:
            raise error.TestFail("Got unexpected format of image '%s'"
                                 " in info test" % image_name)
        if not image_size in img_info:
            raise error.TestFail("Got unexpected size of image '%s'"
                                 " in info test" % image_name)


    def snapshot_test(cmd):
        """
        Subcommand 'qemu-img snapshot' test.

        @param cmd: qemu-img base command.
        """
        cmd += " snapshot"
        for i in range(2):
            crtcmd = cmd
            sn_name = "snapshot%d" % i
            crtcmd += " -c %s %s" % (sn_name, image_name)
            s, o = commands.getstatusoutput(crtcmd)
            if s != 0:
                raise error.TestFail("Create snapshot failed via command: %s;"
                                     "Output is: %s" % (crtcmd, o))
            logging.info("Created snapshot '%s' in '%s'", sn_name, image_name)
        listcmd = cmd
        listcmd += " -l %s" % image_name
        s, o = commands.getstatusoutput(listcmd)
        if not ("snapshot0" in o and "snapshot1" in o and s == 0):
            raise error.TestFail("Snapshot created failed or missed;"
                                 "snapshot list is: \n%s" % o)
        for i in range(2):
            sn_name = "snapshot%d" % i
            delcmd = cmd
            delcmd += " -d %s %s" % (sn_name, image_name)
            s, o = commands.getstatusoutput(delcmd)
            if s != 0:
                raise error.TestFail("Delete snapshot '%s' failed: %s" %
                                                     (sn_name, o))


    def commit_test(cmd):
        """
        Subcommand 'qemu-img commit' test.
        1) Create a backing file of the qemu harddisk specified by image_name.
        2) Start a VM using the backing file as its harddisk.
        3) Touch a file "commit_testfile" in the backing_file, and shutdown the
           VM.
        4) Make sure touching the file does not affect the original harddisk.
        5) Commit the change to the original harddisk by executing
           "qemu-img commit" command.
        6) Start the VM using the original harddisk.
        7) Check if the file "commit_testfile" exists.

        @param cmd: qemu-img base command.
        """
        cmd += " commit"

        logging.info("Commit testing started!")
        image_name = params.get("image_name", "image")
        image_format = params.get("image_format", "qcow2")
        backing_file_name = "%s_bak" % (image_name)

        try:
            # Remove the existing backing file
            backing_file = "%s.%s" % (backing_file_name, image_format)
            if os.path.isfile(backing_file):
                os.remove(backing_file)

            # Create the new backing file
            create_cmd = "qemu-img create -b %s.%s -f %s %s.%s" % (image_name,
                                                                  image_format,
                                                                  image_format,
                                                             backing_file_name,
                                                                  image_format)
            try:
                utils.system(create_cmd)
            except error.CmdError, e:
                raise error.TestFail("Could not create a backing file!")
            logging.info("backing_file created!")

            # Set the qemu harddisk to the backing file
            logging.info("Original image_name is: %s", params.get('image_name'))
            params['image_name'] = backing_file_name
            logging.info("Param image_name changed to: %s",
                         params.get('image_name'))

            # Start a new VM, using backing file as its harddisk
            vm_name = params.get('main_vm')
            virt_env_process.preprocess_vm(test, params, env, vm_name)
            vm = env.get_vm(vm_name)
            vm.create()
            timeout = int(params.get("login_timeout", 360))
            session = vm.wait_for_login(timeout=timeout)

            # Do some changes to the backing_file harddisk
            try:
                output = session.cmd("touch /commit_testfile")
                logging.info("Output of touch /commit_testfile: %s", output)
                output = session.cmd("ls / | grep commit_testfile")
                logging.info("Output of ls / | grep commit_testfile: %s",
                             output)
            except Exception, e:
                raise error.TestFail("Could not create commit_testfile in the "
                                     "backing file %s", e)
            vm.destroy()

            # Make sure there is no effect on the original harddisk
            # First, set the harddisk back to the original one
            logging.info("Current image_name is: %s", params.get('image_name'))
            params['image_name'] = image_name
            logging.info("Param image_name reverted to: %s",
                         params.get('image_name'))

            # Second, Start a new VM, using image_name as its harddisk
            # Here, the commit_testfile should not exist
            vm_name = params.get('main_vm')
            virt_env_process.preprocess_vm(test, params, env, vm_name)
            vm = env.get_vm(vm_name)
            vm.create()
            timeout = int(params.get("login_timeout", 360))
            session = vm.wait_for_login(timeout=timeout)
            try:
                output = session.cmd("[ ! -e /commit_testfile ] && echo $?")
                logging.info("Output of [ ! -e /commit_testfile ] && echo $?: "
                             "%s", output)
            except:
                output = session.cmd("rm -f /commit_testfile")
                raise error.TestFail("The commit_testfile exists on the "
                                     "original file")
            vm.destroy()

            # Excecute the commit command
            logging.info("Commiting image")
            cmitcmd = "%s -f %s %s.%s" % (cmd, image_format, backing_file_name,
                                          image_format)
            try:
                utils.system(cmitcmd)
            except error.CmdError, e:
                raise error.TestFail("Could not commit the backing file")

            # Start a new VM, using image_name as its harddisk
            vm_name = params.get('main_vm')
            virt_env_process.preprocess_vm(test, params, env, vm_name)
            vm = env.get_vm(vm_name)
            vm.create()
            timeout = int(params.get("login_timeout", 360))
            session = vm.wait_for_login(timeout=timeout)
            try:
                output = session.cmd("[ -e /commit_testfile ] && echo $?")
                logging.info("Output of [ -e /commit_testfile ] && echo $?: %s",
                             output)
                session.cmd("rm -f /commit_testfile")
            except:
                raise error.TestFail("Could not find commit_testfile after a "
                                     "commit")
            vm.destroy()

        finally:
            # Remove the backing file
            if os.path.isfile(backing_file):
                os.remove(backing_file)


    def _rebase(cmd, img_name, base_img, backing_fmt, mode="unsafe"):
        """
        Simple wrapper of 'qemu-img rebase'.

        @param cmd: qemu-img base command.
        @param img_name: image name to be rebased
        @param base_img: indicates the base image
        @param backing_fmt: the format of base image
        @param mode: rebase mode: safe mode, unsafe mode
        """
        cmd += " rebase"
        if mode == "unsafe":
            cmd += " -u"
        cmd += " -b %s -F %s %s" % (base_img, backing_fmt, img_name)
        logging.info("Trying to rebase '%s' to '%s'...", img_name, base_img)
        s, o = commands.getstatusoutput(cmd)
        if s != 0:
            raise error.TestError("Failed to rebase '%s' to '%s': %s" %
                                               (img_name, base_img, o))


    def rebase_test(cmd):
        """
        Subcommand 'qemu-img rebase' test

        Change the backing file of a snapshot image in "unsafe mode":
        Assume the previous backing file had missed and we just have to change
        reference of snapshot to new one. After change the backing file of a
        snapshot image in unsafe mode, the snapshot should work still.

        @param cmd: qemu-img base command.
        """
        if not 'rebase' in utils.system_output(cmd + ' --help',
                                               ignore_status=True):
            raise error.TestNAError("Current kvm user space version does not"
                                    " support 'rebase' subcommand")
        sn_fmt = params.get("snapshot_format", "qcow2")
        sn1 = params.get("image_name_snapshot1")
        sn1 = virt_utils.get_path(test.bindir, sn1) + ".%s" % sn_fmt
        base_img = virt_vm.get_image_filename(params, test.bindir)
        _create(cmd, sn1, sn_fmt, base_img=base_img, base_img_fmt=image_format)

        # Create snapshot2 based on snapshot1
        sn2 = params.get("image_name_snapshot2")
        sn2 = virt_utils.get_path(test.bindir, sn2) + ".%s" % sn_fmt
        _create(cmd, sn2, sn_fmt, base_img=sn1, base_img_fmt=sn_fmt)

        rebase_mode = params.get("rebase_mode")
        if rebase_mode == "unsafe":
            os.remove(sn1)

        _rebase(cmd, sn2, base_img, image_format, mode=rebase_mode)

        # Check sn2's format and backing_file
        actual_base_img = _info(cmd, sn2, "backing file")
        base_img_name = os.path.basename(params.get("image_name"))
        if not base_img_name in actual_base_img:
            raise error.TestFail("After rebase the backing_file of 'sn2' is "
                                 "'%s' which is not expected as '%s'"
                                 % (actual_base_img, base_img_name))
        s, o = _check(cmd, sn2)
        if not s:
            raise error.TestFail("Check image '%s' failed after rebase;"
                                 "got error: %s" % (sn2, o))
        try:
            os.remove(sn2)
            os.remove(sn1)
        except:
            pass


    # Here starts test
    subcommand = params.get("subcommand")
    eval("%s_test(cmd)" % subcommand)
