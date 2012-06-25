import re, os, logging, commands, string, time
from autotest.client.shared import utils, error
from autotest.client.virt import kvm_monitor, virt_utils, virt_vm, aexpect
from autotest.client.virt import virt_env_process

@error.context_aware
def run_block_stream(test, params, env):
    """
    Test block streaming functionality.

    1) Create a image_bak.img with the backing file image.img
    2) Start the image_bak.img in qemu command line.
    3) Request for block-stream ide0-hd0/virtio0
    4) Wait till the block job finishs
    5) Check for backing file in image_bak.img
    6) TODO: Check for the size of the image_bak.img should not exceeds the image.img
    7) TODO(extra): Block job completion can be check in QMP
    """
    image_format = params.get("image_format")
    image_name = params.get("image_name", "image")
    drive_format = params.get("drive_format")
    backing_file_name = "%s_bak" % (image_name)
    qemu_img = params.get("qemu_img_binary")

    def check_block_jobs_info():
        """
        Verify the status of block-jobs reported by monitor command info block-jobs.
        @return: parsed output of info block-jobs
        """
        fail = 0

        try:
            output = vm.monitor.info("block-jobs")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
            fail += 1
            return None, None
        return (re.match("\w+", str(output)), re.findall("\d+", str(output)))

    try:
        # Remove the existing backing file
        backing_file = "%s.%s" % (backing_file_name, image_format)
        if os.path.isfile(backing_file):
            os.remove(backing_file)

        # Create the new backing file
        create_cmd = "%s create -b %s.%s -f %s %s.%s" % (qemu_img,
                                                         image_name,
                                                         image_format,
                                                         image_format,
                                                         backing_file_name,
                                                         image_format)
        error.context("Creating backing file")
        utils.system(create_cmd)

        info_cmd = "%s info %s.%s" % (qemu_img,image_name,image_format)
        error.context("Image file can not be find")
        results = utils.system_output(info_cmd)
        logging.info("Infocmd output of basefile: %s" ,results)

        # Set the qemu harddisk to the backing file
        logging.info("Original image_name is: %s", params.get('image_name'))
        params['image_name'] = backing_file_name
        logging.info("Param image_name changed to: %s",
                     params.get('image_name'))

        # Start virtual machine, using backing file as its harddisk
        vm_name = params.get('main_vm')
        virt_env_process.preprocess_vm(test, params, env, vm_name)
        vm = env.get_vm(vm_name)
        vm.create()
        timeout = int(params.get("login_timeout", 360))
        session = vm.wait_for_login(timeout=timeout)

        info_cmd = "%s info %s.%s" % (qemu_img, backing_file_name, image_format)
        error.context("Image file can not be find")
        results = utils.system_output(info_cmd)
        logging.info("Infocmd output of backing file before block streaming: "
                     "%s", results)

        if not re.search("backing file:", str(results)):
           raise error.TestFail("Backing file is not available in the "
                                "backdrive image")

        # Start streaming in qemu-cmd line
        if 'ide' in drive_format:
            error.context("Block streaming on qemu monitor (ide drive)")
            vm.monitor.cmd("block-stream ide0-hd0")
        elif 'virtio' in drive_format:
            error.context("Block streaming on qemu monitor (virtio drive)")
            vm.monitor.cmd("block-stream virtio0")
        else:
            raise error.TestError("The drive format is not supported")

        while True:
            blkjobout, blkjobstatus = check_block_jobs_info()
            if 'Streaming' in blkjobout.group(0):
                logging.info("[(Completed bytes): %s (Total bytes): %s "
                             "(Speed in bytes/s): %s]", blkjobstatus[-3],
                             blkjobstatus[-2], blkjobstatus[-1])
                time.sleep(10)
                continue
            if 'No' in blkjobout.group(0):
                logging.info("Block job completed")
                break

        info_cmd = "%s info %s.%s" % (qemu_img,backing_file_name,image_format)
        error.context("Image file can not be find")
        results = utils.system_output(info_cmd)
        logging.info("Infocmd output of backing file after block streaming: %s",
                     results)

        if re.search("backing file:", str(results)):
           raise error.TestFail(" Backing file is still available in the "
                                "backdrive image")
        # TODO
        # The file size should be more/less equal to the "backing file" size

        # Shutdown the virtual machine
        vm.destroy()

        # Relogin with the backup-harddrive
        vm.create()
        timeout = int(params.get("login_timeout", 360))
        session = vm.wait_for_login(timeout=timeout)
        logging.info("Checking whether the guest with backup-harddrive boot "
                     "and respond after block stream completion")
        error.context("checking responsiveness of guest")
        session.cmd(params.get("alive_test_cmd"))

        # Finally shutdown the virtual machine
        vm.destroy()
    finally:
        # Remove the backing file
        if os.path.isfile(backing_file):
            os.remove(backing_file)
