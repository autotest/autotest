import logging
import os
import re
import signal

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client import utils, os_dep
from autotest.client.shared import error
from autotest.client.shared.utils import VersionableClass


class ServiceManagerInterface(VersionableClass):

    def __new__(cls, *args, **kargs):
        ServiceManagerInterface.master_class = ServiceManagerInterface
        return super(ServiceManagerInterface, cls).__new__(cls, *args, **kargs)

    @classmethod
    def get_version(cls):
        """
        Get version of ServiceManager.
        :return: Version of ServiceManager.
        """
        return open("/proc/1/comm", "r").read().strip()

    def stop(self, service_name):
        raise NotImplementedError("Method 'stop' must be"
                                  " implemented in child class")

    def start(self, service_name):
        raise NotImplementedError("Method 'start' must be"
                                  " implemented in child class")

    def restart(self, service_name):
        raise NotImplementedError("Method 'restart' must be"
                                  " implemented in child class")

    def status(self, service_name):
        raise NotImplementedError("Method 'status' must be"
                                  " implemented in child class")


class ServiceManagerSystemD(ServiceManagerInterface, VersionableClass):

    @classmethod
    def is_right_version(cls, version):
        if version == "systemd":
            return True
        return False

    def stop(self, service_name):
        utils.run("systemctl stop %s.service" % (service_name))

    def start(self, service_name):
        utils.run("systemctl start %s.service" % (service_name))

    def restart(self, service_name):
        utils.run("systemctl restart %s.service" % (service_name))

    def status(self, service_name):
        utils.run("systemctl show %s.service" % (service_name))


class ServiceManagerSysvinit(ServiceManagerInterface, VersionableClass):

    @classmethod
    def is_right_version(cls, version):
        if version == "init":
            return True
        return False

    def stop(self, service_name):
        utils.run("/etc/init.d/%s stop" % (service_name))

    def start(self, service_name):
        utils.run("/etc/init.d/%s start" % (service_name))

    def restart(self, service_name):
        utils.run("/etc/init.d/%s restart" % (service_name))


class ServiceManager(ServiceManagerInterface):
    pass


class OpenVSwitchControl(object):

    """
    Class select the best matches control class for installed version
    of OpenVSwitch.

    OpenVSwtich parameters are described in man ovs-vswitchd.conf.db
    """
    def __new__(cls, db_path=None, db_socket=None, db_pidfile=None,
                ovs_pidfile=None, dbschema=None, install_prefix=None):
        """
        Makes initialization of OpenVSwitch.

        :param tmpdir: Tmp directory for save openvswitch test files.
        :param db_path: Path of OVS databimpoty ase.
        :param db_socket: Path of OVS db socket.
        :param db_pidfile: Path of OVS db ovsdb-server pid.
        :param ovs_pidfile: Path of OVS ovs-vswitchd pid.
        :param install_prefix: Path where is openvswitch installed.
        """
        # if path is None set default path.
        if not install_prefix:
            install_prefix = "/"
        if not db_path:
            db_path = os.path.join(install_prefix,
                                   "/etc/openvswitch/conf.db")
        if not db_socket:
            db_socket = os.path.join(install_prefix,
                                     "/var/run/openvswitch/db.sock")
        if not db_pidfile:
            db_pidfile = os.path.join(install_prefix,
                                      "/var/run/openvswitch/ovsdb-server.pid")
        if not ovs_pidfile:
            ovs_pidfile = os.path.join(install_prefix,
                                       "/var/run/openvswitch/ovs-vswitchd.pid")
        if not dbschema:
            dbschema = os.path.join(install_prefix,
                                    "/usr/share/openvswitch/vswitch.ovsschema")

        OpenVSwitchControl.install_prefix = install_prefix

        OpenVSwitchControl.db_path = db_path
        OpenVSwitchControl.db_socket = db_socket
        OpenVSwitchControl.db_pidfile = db_pidfile
        OpenVSwitchControl.ovs_pidfile = ovs_pidfile

        OpenVSwitchControl.dbschema = install_prefix, dbschema
        os.environ["PATH"] = (os.path.join(install_prefix, "usr/bin:") +
                              os.environ["PATH"])
        os.environ["PATH"] = (os.path.join(install_prefix, "usr/sbin:") +
                              os.environ["PATH"])

        return super(OpenVSwitchControl, cls).__new__(cls)

    @staticmethod
    def convert_version_to_int(version):
        """
        :param version: (int) Converted from version string 1.4.0 => int 140
        """
        if isinstance(version, int):
            return version
        try:
            a = re.findall('^(\d+)\.?(\d+)\.?(\d+)\-?', version)[0]
            int_ver = ''.join(a)
        except:
            raise error.AutotestError("Wrong version format '%s'" % version)
        return int_ver

    @classmethod
    def get_version(cls):
        """
        Get version of installed OpenVSwtich.

        :return: Version of OpenVSwtich.
        """
        version = None
        try:
            result = utils.run(os_dep.command("ovs-vswitchd"),
                               args=["--version"])
            pattern = "ovs-vswitchd \(Open vSwitch\) (.+)"
            version = re.search(pattern, result.stdout).group(1)
        except error.CmdError:
            logging.debug("OpenVSwitch is not available in system.")
        return version

    def status(self):
        raise NotImplementedError()

    def add_br(self, br_name):
        raise NotImplementedError()

    def del_br(self, br_name):
        raise NotImplementedError()

    def br_exist(self, br_name):
        raise NotImplementedError()

    def list_br(self):
        raise NotImplementedError()

    def add_port(self, br_name, port_name):
        raise NotImplementedError()

    def del_port(self, br_name, port_name):
        raise NotImplementedError()

    def add_port_tag(self, port_name, tag):
        raise NotImplementedError()

    def add_port_trunk(self, port_name, trunk):
        raise NotImplementedError()

    def set_vlanmode(self, port_name, vlan_mode):
        raise NotImplementedError()

    def check_port_in_br(self, br_name, port_name):
        raise NotImplementedError()


class OpenVSwitchControlCli(OpenVSwitchControl, VersionableClass):

    """
    Class select the best matches control class for installed version
    of OpenVSwitch.
    """
    def __new__(cls, db_path=None, db_socket=None, db_pidfile=None,
                ovs_pidfile=None, dbschema=None, install_prefix=None):
        OpenVSwitchControlCli.master_class = OpenVSwitchControlCli
        return super(OpenVSwitchControlCli, cls).__new__(cls, db_path,
                                                         db_socket,
                                                         db_pidfile,
                                                         ovs_pidfile,
                                                         dbschema,
                                                         install_prefix)


class OpenVSwitchControlDB(OpenVSwitchControl, VersionableClass):

    """
    Class select the best matches control class for installed version
    of OpenVSwitch.
    """

    def __new__(cls, db_path=None, db_socket=None, db_pidfile=None,
                ovs_pidfile=None, dbschema=None, install_prefix=None):
        OpenVSwitchControlDB.master_class = OpenVSwitchControlDB
        return super(OpenVSwitchControlDB, cls).__new__(cls, db_path,
                                                        db_socket,
                                                        db_pidfile,
                                                        ovs_pidfile,
                                                        dbschema,
                                                        install_prefix)


class OpenVSwitchControlDB_140(OpenVSwitchControlDB, VersionableClass):

    """
    Don't use this class directly. This class is automatically selected by
    OpenVSwitchControl.
    """
    @classmethod
    def is_right_version(cls, version):
        """
        Check condition for select control class.

        :param version: version of OpenVSwtich
        """
        if version is not None:
            int_ver = cls.convert_version_to_int(version)
            if int_ver <= 140:
                return True
        return False

    # TODO: implement database manipulation methods.


class OpenVSwitchControlCli_140(OpenVSwitchControlCli, VersionableClass):

    """
    Don't use this class directly. This class is automatically selected by
    OpenVSwitchControl.
    """
    @classmethod
    def is_right_version(cls, version):
        """
        Check condition for select control class.

        :param version: version of OpenVSwtich
        """
        if version is not None:
            int_ver = cls.convert_version_to_int(version)
            if int_ver <= 140:
                return True
        return False

    def ovs_vsctl(self, parmas, ignore_status=False):
        return utils.run(os_dep.command("ovs-vsctl"), timeout=10,
                         ignore_status=ignore_status, verbose=False,
                         args=["--db=unix:%s" % (self.db_socket)] + parmas)

    def status(self):
        return self.ovs_vsctl(["show"]).stdout

    def add_br(self, br_name):
        self.ovs_vsctl(["add-br", br_name])

    def add_fake_br(self, br_name, parent, vlan):
        self.ovs_vsctl(["add-br", br_name, parent, vlan])

    def del_br(self, br_name):
        try:
            self.ovs_vsctl(["del-br", br_name])
        except error.CmdError, e:
            logging.debug(e.result_obj)
            raise

    def br_exist(self, br_name):
        try:
            self.ovs_vsctl(["br-exists", br_name])
        except error.CmdError, e:
            if e.result_obj.exit_status == 2:
                return False
            else:
                raise
        return True

    def list_br(self):
        return self.ovs_vsctl(["list-br"]).stdout.splitlines()

    def add_port(self, br_name, port_name):
        self.ovs_vsctl(["add-port", br_name, port_name])

    def del_port(self, br_name, port_name):
        self.ovs_vsctl(["del-port", br_name, port_name])

    def add_port_tag(self, port_name, tag):
        self.ovs_vsctl(["set", "Port", port_name, "tag=%s" % tag])

    def add_port_trunk(self, port_name, trunk):
        """
        :param trunk: list of vlans id.
        """
        trunk = map(lambda x: str(x), trunk)
        trunk = "[" + ",".join(trunk) + "]"
        self.ovs_vsctl(["set", "Port", port_name, "trunk=%s" % trunk])

    def set_vlanmode(self, port_name, vlan_mode):
        self.ovs_vsctl(["set", "Port", port_name, "vlan-mode=%s" % vlan_mode])

    def list_ports(self, br_name):
        return self.ovs_vsctl(["list-ports", br_name]).stdout.splitlines()

    def port_to_br(self, port_name):
        """
        Return bridge which contain port.

        :param port_name: Name of port.
        :return: Bridge name or None if there is no bridge which contain port.
        """
        bridge = None
        try:
            bridge = self.ovs_vsctl(["port-to-br", port_name]).stdout
        except error.CmdError, e:
            if e.result_obj.exit_status == 1:
                pass
        return bridge


class OpenVSwitchSystem(OpenVSwitchControlCli, OpenVSwitchControlDB):

    """
    OpenVSwtich class.
    """
    def __new__(cls, db_path=None, db_socket=None, db_pidfile=None,
                ovs_pidfile=None, dbschema=None, install_prefix=None):
        return super(OpenVSwitchSystem, cls).__new__(cls, db_path, db_socket,
                                                     db_pidfile, ovs_pidfile,
                                                     dbschema, install_prefix)

    def __init__(self, db_path=None, db_socket=None, db_pidfile=None,
                 ovs_pidfile=None, dbschema=None, install_prefix=None):
        """
        Makes initialization of OpenVSwitch.

        :param db_path: Path of OVS database.
        :param db_socket: Path of OVS db socket.
        :param db_pidfile: Path of OVS db ovsdb-server pid.
        :param ovs_pidfile: Path of OVS ovs-vswitchd pid.
        :param install_prefix: Path where is openvswitch installed.
        """
        super(OpenVSwitchSystem, self).__init__(self, db_path, db_socket,
                                                db_pidfile, ovs_pidfile,
                                                dbschema, install_prefix)

        self.cleanup = False
        self.pid_files_path = None

    def is_installed(self):
        """
        Check if OpenVSwitch is already installed in system on default places.

        :return: Version of OpenVSwtich.
        """
        if self.get_version():
            return True
        else:
            return False

    def check_db_daemon(self):
        """
        Check if OVS daemon is started correctly.
        """
        working = utils.program_is_alive("ovsdb-server", self.pid_files_path)
        if not working:
            logging.error("OpenVSwitch database daemon with PID in file %s"
                          " not working.", self.db_pidfile)
        return working

    def check_switch_daemon(self):
        """
        Check if OVS daemon is started correctly.
        """
        working = utils.program_is_alive("ovs-vswitchd", self.pid_files_path)
        if not working:
            logging.error("OpenVSwitch switch daemon with PID in file %s"
                          " not working.", self.ovs_pidfile)
        return working

    def check_db_file(self):
        """
        Check if db_file exists.
        """
        exists = os.path.exists(self.db_path)
        if not exists:
            logging.error("OpenVSwitch database file %s not exists.",
                          self.db_path)
        return exists

    def check_db_socket(self):
        """
        Check if db socket exists.
        """
        exists = os.path.exists(self.db_socket)
        if not exists:
            logging.error("OpenVSwitch database socket file %s not exists.",
                          self.db_socket)
        return exists

    def check(self):
        return (self.check_db_daemon() and self.check_switch_daemon() and
                self.check_db_file() and self.check_db_socket())

    def init_system(self):
        """
        Create new dbfile without any configuration.
        """
        sm = ServiceManager()
        try:
            if utils.load_module("openvswitch"):
                sm.restart("openvswitch")
        except error.CmdError:
            logging.error("Service OpenVSwitch is probably not"
                          " installed in system.")
            raise
        self.pid_files_path = "/var/run/openvswitch/"

    def clean(self):
        """
        Empty cleanup function
        """
        pass


class OpenVSwitch(OpenVSwitchSystem):

    """
    OpenVSwtich class.
    """
    def __new__(cls, tmpdir, db_path=None, db_socket=None, db_pidfile=None,
                ovs_pidfile=None, dbschema=None, install_prefix=None):
        return super(OpenVSwitch, cls).__new__(cls, db_path, db_socket,
                                               db_pidfile, ovs_pidfile,
                                               dbschema, install_prefix)

    def __init__(self, tmpdir, db_path=None, db_socket=None, db_pidfile=None,
                 ovs_pidfile=None, dbschema=None, install_prefix=None):
        """
        Makes initialization of OpenVSwitch.

        :param tmpdir: Tmp directory for save openvswitch test files.
        :param db_path: Path of OVS database.
        :param db_socket: Path of OVS db socket.
        :param db_pidfile: Path of OVS db ovsdb-server pid.
        :param ovs_pidfile: Path of OVS ovs-vswitchd pid.
        :param install_prefix: Path where is openvswitch installed.
        """
        super(OpenVSwitch, self).__init__(db_path, db_socket, db_pidfile,
                                          ovs_pidfile, dbschema, install_prefix)
        self.tmpdir = "/%s/openvswitch" % (tmpdir)
        try:
            os.mkdir(self.tmpdir)
        except OSError, e:
            if e.errno != 17:
                raise

    def init_db(self):
        utils.run(os_dep.command("ovsdb-tool"), timeout=10,
                  args=["create", self.db_path, self.dbschema])
        utils.run(os_dep.command("ovsdb-server"), timeout=10,
                  args=["--remote=punix:%s" % (self.db_socket),
                        "--remote=db:Open_vSwitch,manager_options",
                        "--pidfile=%s" % (self.db_pidfile),
                        "--detach"])
        self.ovs_vsctl(["--no-wait", "init"])

    def start_ovs_vswitchd(self):
        utils.run(os_dep.command("ovs-vswitchd"), timeout=10,
                  args=["--detach",
                        "--pidfile=%s" % (self.ovs_pidfile),
                        "unix:%s" % (self.db_socket)])

    def init_new(self):
        """
        Create new dbfile without any configuration.
        """
        self.db_path = os.path.join(self.tmpdir, "conf.db")
        self.db_socket = os.path.join(self.tmpdir, "db.sock")
        self.db_pidfile = utils.get_pid_path("ovsdb-server")
        self.ovs_pidfile = utils.get_pid_path("ovs-vswitchd")
        self.dbschema = "/usr/share/openvswitch/vswitch.ovsschema"

        self.cleanup = True
        sm = ServiceManager()
        # Stop system openvswitch
        try:
            sm.stop("openvswitch")
        except error.CmdError:
            pass
        utils.load_module("openvswitch")
        self.clean()
        if (os.path.exists(self.db_path)):
            os.remove(self.db_path)

        self.init_db()
        self.start_ovs_vswitchd()

    def clean(self):
        logging.debug("Killall ovsdb-server")
        utils.signal_program("ovsdb-server")
        if (utils.program_is_alive("ovsdb-server")):
            utils.signal_program("ovsdb-server", signal.SIGKILL)
        logging.debug("Killall ovs-vswitchd")
        utils.signal_program("ovs-vswitchd")
        if (utils.program_is_alive("ovs-vswitchd")):
            utils.signal_program("ovs-vswitchd", signal.SIGKILL)
