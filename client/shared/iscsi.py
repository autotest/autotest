"""
Basic iscsi support for Linux host with the help of commands
iscsiadm and tgtadm.

This include the basic operates such as login and get device name by
target name. And it can support the real iscsi access and emulated
iscsi in localhost then access it.
"""

import logging
import os
import re

from autotest.client import os_dep
from autotest.client.shared import utils, error


def iscsi_get_sessions():
    """
    Get the iscsi sessions activated
    """
    cmd = "iscsiadm --mode session"

    output = utils.system_output(cmd, ignore_status=True)
    sessions = []
    if "No active sessions" not in output:
        for session in output.splitlines():
            ip_addr = session.split()[2].split(',')[0]
            target = session.split()[3]
            sessions.append((ip_addr, target))
    return sessions


def iscsi_get_nodes():
    """
    Get the iscsi nodes
    """
    cmd = "iscsiadm --mode node"

    output = utils.system_output(cmd)
    pattern = r"(\d+\.\d+\.\d+\.\d+|\W:{2}\d\W):\d+,\d+\s+([\w\.\-:\d]+)"
    nodes = []
    if "No records found" not in output:
        nodes = re.findall(pattern, output)
    return nodes


def iscsi_login(target_name):
    """
    Login to a target with the target name

    :param target_name: Name of the target
    """
    cmd = "iscsiadm --mode node --login --targetname %s" % target_name
    output = utils.system_output(cmd)

    target_login = ""
    if "successful" in output:
        target_login = target_name

    return target_login


def iscsi_logout(target_name=None):
    """
    Logout from a target. If the target name is not set then logout all
    targets.

    :params target_name: Name of the target.
    """
    if target_name:
        cmd = "iscsiadm --mode node --logout -T %s" % target_name
    else:
        cmd = "iscsiadm --mode node --logout all"
    output = utils.system_output(cmd)

    target_logout = ""
    if "successful" in output:
        target_logout = target_name

    return target_logout


def iscsi_discover(portal_ip):
    """
    Query from iscsi server for available targets

    :param portal_ip: Ip for iscsi server
    """
    cmd = "iscsiadm -m discovery -t sendtargets -p %s" % portal_ip
    output = utils.system_output(cmd, ignore_status=True)

    session = ""
    if "Invalid" in output:
        logging.debug(output)
    else:
        session = output
    return session


class Iscsi(object):

    """
    Basic iscsi support class. Will handle the emulated iscsi export and
    access to both real iscsi and emulated iscsi device.
    """

    def __init__(self, params, root_dir="/tmp"):
        os_dep.command("iscsiadm")
        self.target = params.get("target")
        self.export_flag = False
        if params.get("portal_ip"):
            self.portal_ip = params.get("portal_ip")
        else:
            self.portal_ip = utils.system_output("hostname")
        if params.get("iscsi_thread_id"):
            self.id = params.get("iscsi_thread_id")
        else:
            self.id = utils.generate_random_string(4)
        self.initiator = params.get("initiator")
        if params.get("emulated_image"):
            self.initiator = None
            os_dep.command("tgtadm")
            emulated_image = params.get("emulated_image")
            self.emulated_image = os.path.join(root_dir, emulated_image)
            self.emulated_id = ""
            self.emulated_size = params.get("image_size")
            self.unit = self.emulated_size[-1].upper()
            self.emulated_size = self.emulated_size[:-1]
            # maps K,M,G,T => (count, bs)
            emulated_size = {'K': (1, 1),
                             'M': (1, 1024),
                             'G': (1024, 1024),
                             'T': (1024, 1048576),
                             }
            if self.unit in emulated_size:
                block_size = emulated_size[self.unit][1]
                size = int(self.emulated_size) * emulated_size[self.unit][0]
                self.create_cmd = ("dd if=/dev/zero of=%s count=%s bs=%sK"
                                   % (self.emulated_image, size, block_size))

    def logged_in(self):
        """
        Check if the session is login or not.
        """
        sessions = iscsi_get_sessions()
        login = False
        if self.target in map(lambda x: x[1], sessions):
            login = True
        return login

    def portal_visible(self):
        """
        Check if the portal can be found or not.
        """
        return bool(re.findall("%s$" % self.target,
                               iscsi_discover(self.portal_ip), re.M))

    def login(self):
        """
        Login session for both real iscsi device and emulated iscsi. Include
        env check and setup.
        """
        login_flag = False
        if self.portal_visible():
            login_flag = True
        elif self.initiator:
            logging.debug("Try to update iscsi initiatorname")
            cmd = "mv /etc/iscsi/initiatorname.iscsi "
            cmd += "/etc/iscsi/initiatorname.iscsi-%s" % self.id
            utils.system(cmd)
            fd = open("/etc/iscsi/initiatorname.iscsi", 'w')
            fd.write("InitiatorName=%s" % self.initiator)
            fd.close()
            utils.system("service iscsid restart")
            if self.portal_visible():
                login_flag = True
        elif self.emulated_image:
            self.export_target()
            utils.system("service iscsid restart")
            if self.portal_visible():
                login_flag = True

        if login_flag:
            iscsi_login(self.target)

    def get_device_name(self):
        """
        Get device name from the target name.
        """
        cmd = "iscsiadm -m session -P 3"
        device_name = ""
        if self.logged_in():
            output = utils.system_output(cmd)
            pattern = r"Target:\s+%s.*?disk\s(\w+)\s+\S+\srunning" % self.target
            device_name = re.findall(pattern, output, re.S)
            try:
                device_name = "/dev/%s" % device_name[0]
            except IndexError:
                logging.error("Can not find target '%s' after login.", self.target)
        else:
            logging.error("Session is not logged in yet.")
        return device_name

    def get_target_id(self):
        """
        Get target id from image name. Only works for emulated iscsi device
        """
        cmd = "tgtadm --lld iscsi --mode target --op show"
        target_info = utils.system_output(cmd)
        target_id = ""
        for line in re.split("\n", target_info):
            if re.findall("Target\s+(\d+)", line):
                target_id = re.findall("Target\s+(\d+)", line)[0]
            if re.findall("Backing store path:\s+(/+.+)", line):
                if self.emulated_image in line:
                    break
        else:
            target_id = ""

        return target_id

    def export_target(self):
        """
        Export target in localhost for emulated iscsi
        """
        if not os.path.isfile(self.emulated_image):
            utils.system(self.create_cmd)
        cmd = "tgtadm --lld iscsi --mode target --op show"
        try:
            output = utils.system_output(cmd)
        except error.CmdError:
            utils.system("service tgtd restart")
            output = utils.system_output(cmd)
        if not re.findall("%s$" % self.target, output, re.M):
            logging.debug("Need to export target in host")
            output = utils.system_output(cmd)
            used_id = re.findall("Target\s+(\d+)", output)
            emulated_id = 1
            while str(emulated_id) in used_id:
                emulated_id += 1
            self.emulated_id = str(emulated_id)
            cmd = "tgtadm --mode target --op new --tid %s" % self.emulated_id
            cmd += " --lld iscsi --targetname %s" % self.target
            utils.system(cmd)
            cmd = "tgtadm --lld iscsi --op bind --mode target "
            cmd += "--tid %s -I ALL" % self.emulated_id
            utils.system(cmd)
        else:
            target_strs = re.findall("Target\s+(\d+):\s+%s$" %
                                     self.target, output, re.M)
            self.emulated_id = target_strs[0].split(':')[0].split()[-1]

        cmd = "tgtadm --lld iscsi --mode target --op show"
        try:
            output = utils.system_output(cmd)
        except error.CmdError:   # In case service stopped
            utils.system("service tgtd restart")
            output = utils.system_output(cmd)

        # Create a LUN with emulated image
        if re.findall(self.emulated_image, output, re.M):
            # Exist already
            logging.debug("Exported image already exists.")
            self.export_flag = True
            return
        else:
            luns = len(re.findall("\s+LUN:\s(\d+)", output, re.M))
            cmd = "tgtadm --mode logicalunit --op new "
            cmd += "--tid %s --lld iscsi " % self.emulated_id
            cmd += "--lun %s " % luns
            cmd += "--backing-store %s" % self.emulated_image
            utils.system(cmd)
            self.export_flag = True

    def delete_target(self):
        """
        Delete target from host.
        """
        cmd = "tgtadm --lld iscsi --mode target --op show"
        output = utils.system_output(cmd)
        if re.findall("%s$" % self.target, output, re.M):
            if self.emulated_id:
                cmd = "tgtadm --lld iscsi --mode target --op delete "
                cmd += "--tid %s" % self.emulated_id
                utils.system(cmd)

    def logout(self):
        """
        Logout from target.
        """
        if self.logged_in():
            iscsi_logout(self.target)

    def cleanup(self):
        """
        Clean up env after iscsi used.
        """
        self.logout()
        if os.path.isfile("/etc/iscsi/initiatorname.iscsi-%s" % self.id):
            cmd = " mv /etc/iscsi/initiatorname.iscsi-%s" % self.id
            cmd += " /etc/iscsi/initiatorname.iscsi"
            utils.system(cmd)
            cmd = "service iscsid restart"
            utils.system(cmd)
        if self.export_flag:
            self.delete_target()
