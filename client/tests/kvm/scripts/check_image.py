import os, sys, commands


class ImageCheckError(Exception):
    """
    Simple wrapper for the builtin Exception class.
    """
    pass


class ImageCheck(object):
    """
    Check qcow2 image by qemu-img info/check command.
    """
    def __init__(self):
        """
        Gets params from environment variables and sets class attributes.
        """
        self.image_path_list = []
        client_dir =  os.environ['AUTODIR']
        self.kvm_dir = os.path.join(client_dir, 'tests/kvm')
        img_to_check = os.environ['KVM_TEST_images'].split()

        for img in img_to_check:
            img_name_str = "KVM_TEST_image_name_%s" % img
            if not os.environ.has_key(img_name_str):
                img_name_str = "KVM_TEST_image_name"
            img_format_str = "KVM_TEST_image_format_%s" % img
            if os.environ.has_key(img_format_str):
                image_format = os.environ[img_format_str]
            else:
                image_format = os.environ['KVM_TEST_image_format']
            if image_format != "qcow2":
                continue
            image_name = os.environ[img_name_str]
            image_filename = "%s.%s" % (image_name, image_format)
            image_filename = os.path.join(self.kvm_dir, image_filename)
            self.image_path_list.append(image_filename)
        if os.environ.has_key('KVM_TEST_qemu_img_binary'):
            self.qemu_img_path = os.environ['KVM_TEST_qemu_img_binary']
        else:
            self.qemu_img_path = os.path.join(self.kvm_dir, 'qemu-img')
        self.qemu_img_check = True
        cmd = "%s |grep check" % self.qemu_img_path
        (s1, output) = commands.getstatusoutput(cmd)
        if s1:
            self.qemu_img_check = False
            print "Command qemu-img check not available, not checking..."
        cmd = "%s |grep info" % self.qemu_img_path
        (s2, output) = commands.getstatusoutput(cmd)
        if s2:
            self.qemu_img_check = False
            print "Command qemu-img info not available, not checking..."

    def exec_img_cmd(self, cmd_type, image_path):
        """
        Run qemu-img info/check on given image.

        @param cmd_type: Sub command used together with qemu.
        @param image_path: Real path of the image.
        """
        cmd = ' '.join([self.qemu_img_path, cmd_type, image_path])
        print "Checking image with command %s" % cmd
        (status, output) = commands.getstatusoutput(cmd)
        print output
        if status or (cmd_type == "check" and not "No errors" in output):
            msg = "Command %s failed" % cmd
            return False, msg
        else:
            return True, ''


    def check_image(self):
        """
        Run qemu-img info/check to check the image in list.

        If the image checking is failed, raise an exception.
        """
        # Check all the image in list.
        errmsg = []
        for image_path in self.image_path_list:
            s, o = self.exec_img_cmd('info', image_path)
            if not s:
                errmsg.append(o)
            s, o = self.exec_img_cmd('check', image_path)
            if not s:
                errmsg.append(o)

        if len(errmsg) > 0:
            raise ImageCheckError('Errors were found, please check log!')


if __name__ == "__main__":
    image_check = ImageCheck()
    if image_check.qemu_img_check:
        image_check.check_image()
