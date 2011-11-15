import logging, os, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils
from autotest_lib.client.virt import virt_env_process

@error.context_aware
def run_nfs_corrupt(test, params, env):
    """
    Test if VM paused when image NFS shutdown, the drive option 'werror' should
    be stop, the drive option 'cache' should be none.

    1) Setup NFS service on host
    2) Boot up a VM using another disk on NFS server and write the disk by dd
    3) Check if VM status is 'running'
    4) Reject NFS connection on host
    5) Check if VM status is 'paused'
    6) Accept NFS connection on host and continue VM by monitor command
    7) Check if VM status is 'running'

    @param test: kvm test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """

    def setup_nfs_storage(nfs_stat_chk_re="running", force_restart=False):
        nfs_dir = "%s/nfs" % test.tmpdir
        mnt_dir = "%s/images/nfs" % test.bindir
        try:
            os.makedirs(nfs_dir)
            os.makedirs(mnt_dir)
        except OSError:
            pass

        if force_restart:
            utils.run("service nfs restart")
        else:
            # check nfs server status first.
            status = utils.system_output("service nfs status",
                                         ignore_status=True)
            if not re.findall(nfs_stat_chk_re, status):
                utils.run("service nfs start")

        utils.run("exportfs localhost:%s -o rw,no_root_squash" % nfs_dir)
        utils.run("mount localhost:%s %s -o rw,soft,timeo=1,"
                  "retrans=1,vers=3" % (nfs_dir, mnt_dir))

    def cleanup_nfs_storage(force_stop=False):
        nfs_dir = "%s/nfs" % test.tmpdir
        mnt_dir = "%s/images/nfs" % test.bindir
        utils.run("umount %s" % mnt_dir)
        utils.run("exportfs -u localhost:%s" % nfs_dir)
        if force_stop:
            utils.run("service nfs stop")

    def get_nfs_devname(params, session):
        """
        Get the possbile name of nfs storage dev name in guest.
        """
        image1_type = params.object_params("image1").get("drive_format")
        stg_type = params.object_params("stg").get("drive_format")
        cmd = ""
        # Seems we can get correct 'stg' devname even if the 'stg' image
        # has a different type from main image (we call it 'image1' in
        # config file) with these 'if' sentences.
        if image1_type == stg_type:
            cmd = "ls /dev/[hsv]d[a-z]"
        elif stg_type == "virtio":
            cmd = "ls /dev/vd[a-z]"
        else:
            cmd = "ls /dev/[sh]d[a-z]"

        cmd += " |tail -n 1"
        return session.cmd_output(cmd)

    def check_vm_status(vm, status):
        try:
            vm.verify_status(status)
        except:
            return False
        else:
            return True

    nfs_stat_chk_re = params.get("nfs_stat_chk_re")
    error.context("Setup nfs storage on localhost")
    setup_nfs_storage(nfs_stat_chk_re)

    params["image_name_stg"] = "%s/images/nfs/nfs_corrupt" % test.bindir
    params["force_create_image_stg"] = "yes"
    params["create_image_stg"] = "yes"
    stg_params = params.object_params("stg")
    virt_env_process.preprocess_image(test, stg_params)

    vm = env.get_vm(params["main_vm"])
    vm.create(params=params)
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))

    nfs_devname = get_nfs_devname(params, session)

    # Write disk on NFS server
    write_disk_cmd = "dd if=/dev/urandom of=%s" % nfs_devname
    logging.info("Write disk on NFS server, cmd: %s" % write_disk_cmd)
    session.sendline(write_disk_cmd)
    try:
        # Read some command output, it will timeout
        logging.debug(session.read_up_to_prompt(timeout=30))
    except:
        pass

    try:
        error.context("Make sure guest is running before test")
        vm.resume()
        vm.verify_status("running")

        try:
            cmd = "iptables"
            cmd += " -t filter"
            cmd += " -A INPUT"
            cmd += " -s localhost"
            cmd += " -m state"
            cmd += " --state NEW"
            cmd += " -p tcp"
            cmd += " --dport 2049"
            cmd += " -j REJECT"

            error.context("Reject NFS connection on host")
            utils.system(cmd)

            error.context("Check if VM status is 'paused'")
            if not virt_utils.wait_for(
                                lambda: check_vm_status(vm, "paused"),
                                int(params.get('wait_paused_timeout', 120))):
                raise error.TestError("Guest is not paused after stop NFS")
        finally:
            error.context("Accept NFS connection on host")
            cmd = "iptables"
            cmd += " -t filter"
            cmd += " -D INPUT"
            cmd += " -s localhost"
            cmd += " -m state"
            cmd += " --state NEW"
            cmd += " -p tcp"
            cmd += " --dport 2049"
            cmd += " -j REJECT"

            utils.system(cmd)

        error.context("Continue guest")
        vm.resume()

        error.context("Check if VM status is 'running'")
        if not virt_utils.wait_for(lambda: check_vm_status(vm, "running"), 20):
            raise error.TestError("Guest does not restore to 'running' status")

    finally:
        session.close()
        vm.destroy(gracefully=True)
        error.context("Stop NFS service on localhost")
        cleanup_nfs_storage()
