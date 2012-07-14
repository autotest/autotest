import logging, os, re
from autotest.client.shared import error
from autotest.client import utils, os_dep
from autotest.client.virt import virt_utils
from autotest.client.virt import virt_env_process


class NFSCorruptConfig(object):
    """
    This class sets up nfs_corrupt test environment.
    """
    def __init__(self, test, params):
        self.nfs_dir = os.path.join(test.tmpdir, "nfs_dir")
        self.mnt_dir = os.path.join(test.tmpdir, "mnt_dir")
        self.chk_re = params.get("nfs_stat_chk_re", "running")

        cmd_list = self._get_service_cmds()
        self.start_cmd = cmd_list[0]
        self.stop_cmd = cmd_list[1]
        self.restart_cmd = cmd_list[2]
        self.status_cmd = cmd_list[3]

    @error.context_aware
    def _get_service_cmds(self):
        """
        Figure out the commands used to control the NFS service.
        """
        error.context("Finding out appropriate commands to handle NFS service")
        service = os_dep.command("service")
        try:
            systemctl = os_dep.command("systemctl")
        except ValueError:
            systemctl = None

        if systemctl is not None:
            init_script = "/etc/init.d/nfs"
            service_file = "/lib/systemd/system/nfs-server.service"
            if os.path.isfile(init_script):
                service_name = "nfs"
            elif os.path.isfile(service_file):
                service_name = "nfs-server"
            else:
                raise error.TestError("Files %s and %s absent, don't know "
                                      "how to set up NFS for this host" %
                                      (init_script, service_file))
            start_cmd = "%s start %s.service" % (systemctl, service_name)
            stop_cmd = "%s stop %s.service" % (systemctl, service_name)
            restart_cmd = "%s restart %s.service" % (systemctl, service_name)
            status_cmd = "%s status %s.service" % (systemctl, service_name)
        else:
            start_cmd = "%s nfs start" % service
            stop_cmd = "%s nfs stop" % service
            restart_cmd = "%s nfs restart" % service
            status_cmd = "%s nfs status" % service

        return [start_cmd, stop_cmd, restart_cmd, status_cmd]

    @error.context_aware
    def setup(self, force_start=False):
        """
        Setup test NFS share.

        @param force_start: Whether to make NFS service start anyway.
        """
        error.context("Setting up test NFS share")

        for d in [self.nfs_dir, self.mnt_dir]:
            try:
                os.makedirs(d)
            except OSError:
                pass

        if force_start:
            self.start_service()
        else:
            if not self.is_service_active():
                self.start_service()

        utils.run("exportfs localhost:%s -o rw,no_root_squash" % self.nfs_dir)
        utils.run("mount localhost:%s %s -o rw,soft,timeo=1,retrans=1,vers=3" %
                  (self.nfs_dir, self.mnt_dir))

    @error.context_aware
    def cleanup(self, force_stop=False):
        error.context("Cleaning up test NFS share")
        utils.run("umount %s" % self.mnt_dir)
        utils.run("exportfs -u localhost:%s" % self.nfs_dir)
        if force_stop:
            self.stop_service()

    def start_service(self):
        """
        Starts the NFS server.
        """
        utils.run(self.start_cmd)

    def stop_service(self):
        """
        Stops the NFS server.
        """
        utils.run(self.stop_cmd)

    def restart_service(self):
        """
        Restarts the NFS server.
        """
        utils.run(self.restart_cmd)

    def is_service_active(self):
        """
        Verifies whether the NFS server is running or not.

        @param chk_re: Regular expression that tells whether NFS is running
                or not.
        """
        status = utils.system_output(self.status_cmd, ignore_status=True)
        if re.findall(self.chk_re, status):
            return True
        else:
            return False


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
    def get_nfs_devname(params, session):
        """
        Get the possbile name of nfs storage dev name in guest.

        @param params: Test params dictionary.
        @param session: An SSH session object.
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

        cmd += " | tail -n 1"
        return session.cmd_output(cmd)


    def check_vm_status(vm, status):
        """
        Check if VM has the given status or not.

        @param vm: VM object.
        @param status: String with desired status.
        @return: True if VM status matches our desired status.
        @return: False if VM status does not match our desired status.
        """
        try:
            vm.verify_status(status)
        except:
            return False
        else:
            return True


    config = NFSCorruptConfig(test, params)
    config.setup()

    params["image_name_stg"] = os.path.join(config.mnt_dir, 'nfs_corrupt')
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
        session.read_up_to_prompt(timeout=30)
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
        config.cleanup()
