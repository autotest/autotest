import logging, re, random
from autotest_lib.client.common_lib import error


@error.context_aware
def run_multi_disk(test, params, env):
    """
    Test multi disk suport of guest, this case will:
    1) Create disks image in configuration file.
    2) Start the guest with those disks.
    3) Format those disks.
    4) Copy file into / out of those disks.
    5) Compare the original file and the copied file using md5 or fc comand.
    6) Repeat steps 3-5 if needed.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))

    images = params.get("images").split()
    n_repeat = int(params.get("n_repeat", "1"))
    image_num = len(images)
    disk_num = 0
    file_system = params.get("file_system").split()
    fs_num = len(file_system)
    cmd_timeout = float(params.get("cmd_timeout", 360))
    re_str = params.get("re_str")
    block_list = params.get("block_list").split()

    try:
        if params.get("clean_cmd"):
            cmd = params.get("clean_cmd")
            session.cmd_status_output(cmd)
        if params.get("pre_cmd"):
            cmd = params.get("pre_cmd")
            error.context("creating partition on test disk")
            session.cmd(cmd, timeout=cmd_timeout)
        cmd = params.get("list_volume_command")
        output = session.cmd_output(cmd, timeout=cmd_timeout)
        disks = re.findall(re_str, output)
        disks.sort()
        logging.debug("Volume list that meets regular expressions: %s", disks)
        if len(disks) < image_num:
            raise error.TestFail("Fail to list all the volumes!")

        tmp_list = []
        for disk in disks:
            if disk.strip() in block_list:
                tmp_list.append(disk)
        for disk in tmp_list:
            logging.info("No need to check volume %s", disk)
            disks.remove(disk)

        for i in range(n_repeat):
            logging.info("iterations: %s", (i + 1))
            for disk in disks:
                disk = disk.strip()

                logging.info("Format disk: %s..." % disk)
                index = random.randint(0, fs_num - 1)

                # Random select one file system from file_system
                fs = file_system[index].strip()
                cmd = params.get("format_command") % (fs, disk)
                error.context("formatting test disk")
                session.cmd(cmd, timeout=cmd_timeout)
                if params.get("mount_command"):
                    cmd = params.get("mount_command") % (disk, disk, disk)
                    session.cmd(cmd, timeout=cmd_timeout)

            for disk in disks:
                disk = disk.strip()

                logging.info("Performing I/O on disk: %s...", disk)
                cmd_list = params.get("cmd_list").split()
                for cmd_l in cmd_list:
                    if params.get(cmd_l):
                        cmd = params.get(cmd_l) % disk
                        session.cmd(cmd, timeout=cmd_timeout)

                cmd = params.get("compare_command")
                output = session.cmd_output(cmd)
                key_word = params.get("check_result_key_word")
                if key_word and key_word in output:
                    logging.debug("Guest's virtual disk %s works fine", disk)
                elif key_word:
                    raise error.TestFail("Files on guest os root fs and disk "
                                         "differ")
                else:
                    raise error.TestError("Param check_result_key_word was not "
                                          "specified! Please check your config")

            if params.get("umount_command"):
                cmd = params.get("show_mount_cmd")
                output = session.cmd_output(cmd)
                disks = re.findall(re_str, output)
                disks.sort()
                for disk in disks:
                    disk = disk.strip()
                    cmd = params.get("umount_command") % (disk, disk)
                    error.context("unmounting test disk")
                    session.cmd(cmd)
    finally:
        if params.get("post_cmd"):
            cmd = params.get("post_cmd")
            session.cmd(cmd)
        session.close()
