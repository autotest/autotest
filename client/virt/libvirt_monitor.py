import re, tempfile, xml.dom.minidom, logging
import virt_utils, aexpect
from autotest_lib.client import utils


class VirshMonitor:
    """
    Wraps "Virsh monitor" commands.
    """

    LOGIN_TIMEOUT = 10

    def __init__(self, virsh_exec, name, vmname, password=None,
                 prompt=None, hostname='localhost', driver=None, username=None,
                 linesep="\\n"):
        """
        Connect to the hypervisor and get virsh prompt.

        @param virsh_exec: Virsh executable
        @param name: Monitor identifier (a string)
        @param vmname: VM name
        @param password: Hypervisor user password
        @param prompt: Virsh prompt
        @param hostname: Hypervisor IP
        @param driver: Hypervisor driver type
        @param username: Hypervisor  username
        @param linesep: The line separator to use when sending lines
                (e.g. '\\n' or '\\r\\n')
        """
        self.virsh_exec = virsh_exec
        self.name = name
        self.vmname = vmname
        self.password = password
        self.prompt = prompt
        self.hostname = hostname
        self.driver = driver
        self.username = username
        self.session = self.login()
        self.virsh_cmd = {"help":"help", "quit":"destroy " + self.vmname,
                           "stop":"suspend", "cont":"resume"}
        self.drive_map = {}
        self.network_info = []
        self.disk_info = []
        self._parse_domxml()


    def __del__(self):
        self.session.sendline("quit")


    def __getstate__(self):
        pass


    def __setstate__(self, state):
        pass


    def __getinitargs__(self):
        # Save some information when pickling -- will be passed to the
        # constructor upon unpickling
        return (self.name, self.vmname, self.password, self.prompt,
                self.hostname, self.driver, self.username)


    def login(self, timeout=LOGIN_TIMEOUT):
        """
        Log into the hypervisor using required URIs .

        @timeout: Time in seconds that we will wait before giving up on logging
                into the host.
        @return: A ShellSession object.
        """
        if self.driver is None:
            uri = utils.system_output('%s uri' % self.virsh_exec)
        else:
            uri = "%s+ssh://%s@%s/system" % (self.driver, self.username,
                                             self.host)

        command = "%s --connect  %s" % (self.virsh_exec, uri)

        session = aexpect.ShellSession(command, linesep=self.linesep,
                                       prompt=self.prompt)

        if self.username is not None:
            try:
                virt_utils._remote_login(session, self.username, self.password,
                                         self.prompt, timeout)
            except aexpect.ShellError:
                session.close()
                session = None

        return session


    def _parse_domxml(self):
        self.session.cmd_output("\n")
        domxml = self.session.cmd_output("dumpxml %s \n" % self.vmname)
        self._parse_dev(domxml)


    def _parse_dev(self, domxml):
        dom = xml.dom.minidom.parseString(domxml)
        self.network_info = []
        for elems in dom.getElementsByTagName('interface'):
            self.network_info.append(elems.toxml())

        self.disk_info = []
        for elems in dom.getElementsByTagName('disk'):
            self.disk_info.append(elems.toxml())


    def verify_responsive(self):
        """
        Make sure the monitor is responsive by sending a command.
        """
        self.cmd("help")


    def cmd(self, command):
        """
        Send command to the monitor.

        @param command: Command to send to the monitor
        @return: Output received from the monitor
        """
        def dev_add(command):
            """
            Create the xml file for the device to be attached
            """
            parm_dic = dict(re.findall("(id|driver|mac|drive)=([^,\s]+)",
                                         command))
            self.session.cmd_output("\n")
            if parm_dic.has_key("drive"):
                self.drive_map[parm_dic["drive"]]["driver"] = parm_dic\
                                                              ["driver"]
                self.drive_map[parm_dic["drive"]]["device_id"] = parm_dic["id"]
                self.drive_map[parm_dic["drive"]]["dev"] = "vd" + str(len(
                                                              self.drive_map))
                doc = xml.dom.minidom.Document()
                topelem = doc.createElement("disk")
                topelem.setAttribute('device', 'disk')
                topelem.setAttribute('type', 'file')
                doc.appendChild(topelem)
                chld_elem = doc.createElement("driver")
                chld_elem.setAttribute('name', "qemu")
                topelem.appendChild(chld_elem)
                chld_elem = doc.createElement("source")
                chld_elem.setAttribute('file', self.drive_map[parm_dic["drive"]
                                                             ]["file"])
                topelem.appendChild(chld_elem)
                chld_elem = doc.createElement("target")
                if "virtio-blk-pci" in command:
                    self.drive_map[parm_dic["drive"]]["driver"] = "virtio"
                chld_elem.setAttribute('bus', self.drive_map[parm_dic["drive"]
                                                            ]["driver"])
                chld_elem.setAttribute('dev', self.drive_map[parm_dic["drive"]
                                                            ]["dev"])
                topelem.appendChild(chld_elem)
            else:
                netpool_lst = self.session.cmd_output("net-list"
                                                               ).split('\n')
                netpool = []
                for r in range(2, len(netpool_lst) - 2):
                    netpool.append(netpool_lst[r].split()[0])

                doc = xml.dom.minidom.Document()
                topelem = doc.createElement("interface")
                doc.appendChild(topelem)

                chld_elem = doc.createElement("source")
                chld_elem.setAttribute('network', netpool[-1])
                topelem.appendChild(chld_elem)
                if parm_dic.has_key("mac"):
                    mac = parm_dic.get("mac")
                    chld_elem = doc.createElement("mac")
                    chld_elem.setAttribute('address', mac)
                    topelem.appendChild(chld_elem)
                if not parm_dic.has_key("driver"):
                    model = re.findall("device_add ([^,\s]+)", command)[0]
                else:
                    model = parm_dic.get("driver")
                if model == "virtio-net-pci":
                    model = "virtio"
                chld_elem = doc.createElement("model")
                chld_elem.setAttribute('type', model)
                topelem.appendChild(chld_elem)
                if parm_dic.has_key("id"):
                    id = parm_dic.get("id")
                    chld_elem = doc.createElement("target")
                    chld_elem.setAttribute('dev', id)
                    topelem.appendChild(chld_elem)

            tmp_xml = doc.toxml()
            devfl = tempfile.mktemp(prefix='dev')
            devfd = open(devfl, 'w')
            devfd.write(tmp_xml)
            devfd.close()
            return devfl

        def net_del(command):
            """
            Create the xml file for the device to be detached
            """
            xml_str = ""
            id = re.findall("device_del ([^,\s]+)", command)[0]
            for i in range(len(self.network_info)):
                if id in str(self.network_info[i]):
                    xml_str = str(self.network_info[i])
            for i in self.drive_map:
                if id in str(self.drive_map[i]):
                    map_key = self.drive_map[i]["dev"]
                    for i in range(len(self.disk_info)):
                        if map_key in str(self.disk_info[i]):
                            xml_str = str(self.disk_info[i])
            devfl = tempfile.mktemp(prefix='dev')
            devfd = open(devfl, 'w')
            devfd.write(xml_str)
            devfd.close()
            return devfl

        if "device_add ?" in command:
            return "virtio-net-pci virtio-blk-pci e1000 rtl8139"

        if "?" in command:
            output = "\nhelp|? [cmd]\ndevice_add\ndevice_del\ndrive_add"\
                                                "\n__com.redhat_drive_add"
            return output

        if "redhat_drive" in command:
            drive_dic = dict(re.findall("(file|id)=([^,\s]+)", command))
            self.drive_map[drive_dic["id"]] = drive_dic
            return

        if "netdev_add" in command:
            id = re.findall("id=(.*?),", command)[0]
            net_str = " peer=%s" % id
            self.network_info[id] = net_str
            return

        if "device_add"  in command:
            devfile = dev_add(command)
            xml_handle = open(devfile)
            xml_pars = xml.dom.minidom.parse(xml_handle)
            self.session.cmd_output("attach-device %s %s" %
                                    (self.vmname, devfile))
            domxml = self.session.cmd_output("dumpxml %s \n" % self.vmname)
            self._parse_dev(domxml)
            return

        if "device_del" in command:
            devfile = net_del(command)
            xml_handle = open(devfile)
            xml_pars = xml.dom.minidom.parse(xml_handle)
            self.session.cmd_output("detach-device %s %s" %
                                    (self.vmname, devfile))
            domxml = self.session.cmd_output("dumpxml %s \n" % self.vmname)
            self._parse_dev(domxml)
            return

        if "balloon" in command:
            new_mem = re.findall("balloon\s+(\d+)", command)[0]
            new_mem = str(int(new_mem) * 1024)
            output = self.session.cmd_output("setmem  %s %s" %
                                                      (self.vmname, new_mem))
            return

        if "system_reset" in command:
            self.session.cmd_output("destroy %s" % self.vmname)
            self.session.cmd_output("start %s" % self.vmname)
            return

        data = self.session.cmd_output(" %s \n" % self.virsh_cmd.get(
                                                            command, command))
        return data


    def is_responsive(self):
        """
        Return True if the monitor is responsive.
        """
        return True


    def quit(self):
        """
        Send "quit" without waiting for output.
        """
        self.cmd("quit")


    def screendump(self, filename, debug=True):
        """
        Request a screendump.

        @param filename: Location for the screendump
        @return: The command's output
        """
        if debug:
            logging.debug("Requesting screendump %s" % filename)
        return self.cmd("screenshot %s" % filename)


    def info(self, what):
        """
        Request info about something and return the output.
        """
        if "network" in what:
            return self.network_info

        if "pci" in what:
            domxml = self.session.cmd_output("dumpxml %s \n" %
                                                       self.vmname)
            self._parse_dev(domxml)
            return str(self.network_info) + str(self.drive_map)

        if "balloon" in what:
            self.session.cmd_output("\n")
            netpool_lst = self.session.cmd_output("dominfo %s" %
                                                            self.vmname)
            return str(int(re.findall("Used memory:\s+(\d+)", netpool_lst)
                                       [0]) / 1024)

        return self.cmd("info %s" % what)
