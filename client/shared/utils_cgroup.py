#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Helpers for cgroup testing.

:copyright: 2011 Red Hat Inc.
:author: Lukas Doktor <ldoktor@redhat.com>
"""
import logging
import os
import shutil
import subprocess
import time
import re
import random
import commands
from tempfile import mkdtemp
from autotest.client import utils
from autotest.client.shared import error


class Cgroup(object):

    """
    Cgroup handling class.
    """

    def __init__(self, module, _client):
        """
        Constructor
        :param module: Name of the cgroup module
        :param _client: Test script pwd + name
        """
        self.module = module
        self._client = _client
        self.root = None
        self.cgroups = []

    def __del__(self):
        """
        Destructor
        """
        self.cgroups.sort(reverse=True)
        for pwd in self.cgroups[:]:
            for task in self.get_property("tasks", pwd):
                if task:
                    self.set_root_cgroup(int(task))
            self.rm_cgroup(pwd)

    def initialize(self, modules):
        """
        Initializes object for use.

        :param modules: Array of all available cgroup modules.
        """
        self.root = modules.get_pwd(self.module)
        if not self.root:
            raise error.TestError("cg.initialize(): Module %s not found"
                                  % self.module)

    def __get_cgroup_pwd(self, cgroup):
        """
        Get cgroup's full path

        :param: cgroup: cgroup name
        :return: cgroup's full path
        """
        if not isinstance(cgroup, str):
            raise error.TestError("cgroup type isn't string!")
        return os.path.join(self.root, cgroup) + '/'

    def get_cgroup_name(self, pwd=None):
        """
        Get cgroup's name

        :param: pwd: cgroup name
        :return: cgroup's name
        """
        if pwd is None:
            # root cgroup
            return None
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        # self.root is "/cgroup/blkio," not "/cgroup/blkio/"
        # cgroup is "/cgroup/blkio/test" or "/cgroup/blkio/test/test"
        # expected cgroup name is test/ or test/test/
        if pwd.startswith(self.root + '/'):
            return pwd[len(self.root) + 1:]
        return None

    def get_cgroup_index(self, cgroup):
        """
        Get cgroup's index in cgroups

        :param: cgroup: cgroup name
        :return: index of cgroup
        """
        try:
            if self.__get_cgroup_pwd(cgroup) not in self.cgroups:
                raise error.TestFail("%s not exists!" % cgroup)
            cgroup_pwd = self.__get_cgroup_pwd(cgroup)
            return self.cgroups.index(cgroup_pwd)
        except error.CmdError:
            raise error.TestFail("Find index failed!")

    def mk_cgroup_cgcreate(self, pwd=None, cgroup=None):
        """
        Make a cgroup by cgcreate command

        :params: cgroup: Maked cgroup name
        :return: last cgroup index
        """
        try:
            parent_cgroup = self.get_cgroup_name(pwd)
            if cgroup is None:
                range = "abcdefghijklmnopqrstuvwxyz0123456789"
                sub_cgroup = "cgroup-" + "".join(random.sample(range +
                                                 range.upper(), 6))
            else:
                sub_cgroup = cgroup
            if parent_cgroup is None:
                cgroup = sub_cgroup
            else:
                # Parent cgroup:test. Created cgroup:test1.
                # Whole cgroup name is "test/test1"
                cgroup = os.path.join(parent_cgroup, sub_cgroup)
            if self.__get_cgroup_pwd(cgroup) in self.cgroups:
                raise error.TestFail("%s exists!" % cgroup)
            cgcreate_cmd = "cgcreate -g %s:%s" % (self.module, cgroup)
            utils.run(cgcreate_cmd, ignore_status=False)
            pwd = self.__get_cgroup_pwd(cgroup)
            self.cgroups.append(pwd)
            return len(self.cgroups) - 1
        except error.CmdError:
            raise error.TestFail("Make cgroup by cgcreate failed!")

    def mk_cgroup(self, pwd=None, cgroup=None):
        """
        Creates new temporary cgroup
        :param pwd: where to create this cgroup (default: self.root)
        :param cgroup: desired cgroup name
        :return: last cgroup index
        """
        if pwd is None:
            pwd = self.root
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            if cgroup and self.__get_cgroup_pwd(cgroup) in self.cgroups:
                raise error.TestFail("%s exists!" % cgroup)
            if not cgroup:
                pwd = mkdtemp(prefix='cgroup-', dir=pwd) + '/'
            else:
                pwd = os.path.join(pwd, cgroup) + '/'
                if not os.path.exists(pwd):
                    os.mkdir(pwd)
        except Exception, inst:
            raise error.TestError("cg.mk_cgroup(): %s" % inst)
        self.cgroups.append(pwd)
        return len(self.cgroups) - 1

    def cgexec(self, cgroup, cmd, args=""):
        """
        Execute command in desired cgroup

        :param: cgroup: Desired cgroup
        :param: cmd: Executed command
        :param: args: Executed command's parameters
        """
        try:
            args_str = ""
            if len(args):
                args_str = " ".join(args)
            cgexec_cmd = ("cgexec -g %s:%s %s %s" %
                         (self.module, cgroup, cmd, args_str))
            status, output = commands.getstatusoutput(cgexec_cmd)
            return status, output
        except error.CmdError, detail:
            raise error.TestFail("Execute %s in cgroup failed!\n%s" %
                                 (cmd, detail))

    def rm_cgroup(self, pwd):
        """
        Removes cgroup.

        :param pwd: cgroup directory.
        """
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            os.rmdir(pwd)
            self.cgroups.remove(pwd)
        except ValueError:
            logging.warn("cg.rm_cgroup(): Removed cgroup which wasn't created"
                         "using this Cgroup")
        except Exception, inst:
            raise error.TestError("cg.rm_cgroup(): %s" % inst)

    def cgdelete_all_cgroups(self):
        """
        Delete all cgroups in the module
        """
        try:
            for cgroup_pwd in self.cgroups:
                # Ignore sub cgroup
                cgroup = self.get_cgroup_name(cgroup_pwd)
                if cgroup.count("/") > 0:
                    continue
                self.cgdelete_cgroup(cgroup, True)
        except error.CmdError:
            raise error.TestFail("cgdelete all cgroups in %s failed!"
                                 % self.module)

    def cgdelete_cgroup(self, cgroup, recursive=False):
        """
        Delete desired cgroup.

        :params cgroup: desired cgroup
        :params force:If true, sub cgroup can be deleted with parent cgroup
        """
        try:
            cgroup_pwd = self.__get_cgroup_pwd(cgroup)
            if cgroup_pwd not in self.cgroups:
                raise error.TestError("%s doesn't exist!" % cgroup)
            cmd = "cgdelete %s:%s" % (self.module, cgroup)
            if recursive:
                cmd += " -r"
            utils.run(cmd, ignore_status=False)
            self.cgroups.remove(cgroup_pwd)
        except error.CmdError, detail:
            raise error.TestFail("cgdelete %s failed!\n%s" %
                                 (cgroup, detail))

    def cgclassify_cgroup(self, pid, cgroup):
        """
        Classify pid into cgroup

        :param pid: pid of the process
        :param cgroup: cgroup name
        """
        try:
            cgroup_pwd = self.__get_cgroup_pwd(cgroup)
            if cgroup_pwd not in self.cgroups:
                raise error.TestError("%s doesn't exist!" % cgroup)
            cgclassify_cmd = ("cgclassify -g %s:%s %d" %
                             (self.module, cgroup, pid))
            utils.run(cgclassify_cmd, ignore_status=False)
        except error.CmdError, detail:
            raise error.TestFail("Classify process to tasks file failed!:%s" %
                                 detail)

    def get_pids(self, pwd=None):
        """
        Get all pids in cgroup

        :params: pwd: cgroup directory
        :return: all pids(list)
        """
        if pwd is None:
            pwd = self.root
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            return [_.strip() for _ in open(os.path.join(pwd, 'tasks'), 'r')]
        except Exception, inst:
            raise error.TestError("cg.get_pids(): %s" % inst)

    def test(self, cmd):
        """
        Executes cgroup_client.py with cmd parameter.

        :param cmd: command to be executed
        :return: subprocess.Popen() process
        """
        logging.debug("cg.test(): executing parallel process '%s'", cmd)
        cmd = self._client + ' ' + cmd
        process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, close_fds=True)
        return process

    def is_cgroup(self, pid, pwd):
        """
        Checks if the 'pid' process is in 'pwd' cgroup
        :param pid: pid of the process
        :param pwd: cgroup directory
        :return: 0 when is 'pwd' member
        """
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        if open(os.path.join(pwd, 'tasks')).readlines().count("%d\n" % pid) > 0:
            return 0
        else:
            return -1

    def is_root_cgroup(self, pid):
        """
        Checks if the 'pid' process is in root cgroup (WO cgroup)
        :param pid: pid of the process
        :return: 0 when is 'root' member
        """
        return self.is_cgroup(pid, self.root)

    def set_cgroup(self, pid, pwd=None):
        """
        Sets cgroup membership
        :param pid: pid of the process
        :param pwd: cgroup directory
        """
        if pwd is None:
            pwd = self.root
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            open(os.path.join(pwd, 'tasks'), 'w').write(str(pid))
        except Exception, inst:
            raise error.TestError("cg.set_cgroup(): %s" % inst)
        if self.is_cgroup(pid, pwd):
            raise error.TestError("cg.set_cgroup(): Setting %d pid into %s "
                                  "cgroup failed" % (pid, pwd))

    def refresh_cgroups(self):
        """
        Refresh all cgroups path.
        """
        try:
            cgroups = utils.run("lscgroup").stdout.strip()
            cgroup_list = []
            for line in cgroups.splitlines():
                controllers = line.split(":")[0]
                if set(self.module.split(",")) != set(controllers.split(",")):
                    continue
                cgroup_name = line.split(":")[-1]
                if cgroup_name != "/":
                    cgroup_list.append(cgroup_name[1:])
        except error.CmdError:
            raise error.TestFail("Get cgroup in %s failed!" % self.module)

        self.cgroups = []
        for cgroup in cgroup_list:
            pwd = self.__get_cgroup_pwd(cgroup)
            self.cgroups.append(pwd)

    def set_root_cgroup(self, pid):
        """
        Resets the cgroup membership (sets to root)
        :param pid: pid of the process
        :return: 0 when PASSED
        """
        return self.set_cgroup(pid, self.root)

    def get_property(self, prop, pwd=None):
        """
        Gets the property value
        :param prop: property name (file)
        :param pwd: cgroup directory
        :return: [] values or None when FAILED
        """
        if pwd is None:
            pwd = self.root
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            # Remove tailing '\n' from each line
            ret = [_[:-1] for _ in open(os.path.join(pwd, prop), 'r')]
            if ret:
                return ret
            else:
                return [""]
        except Exception, inst:
            raise error.TestError("cg.get_property(): %s" % inst)

    def set_property_h(self, prop, value, pwd=None, check=True, checkprop=None):
        """
        Sets the one-line property value concerning the K,M,G postfix
        :param prop: property name (file)
        :param value: desired value
        :param pwd: cgroup directory
        :param check: check the value after setup / override checking value
        :param checkprop: override prop when checking the value
        """
        _value = value
        try:
            value = str(value)
            human = {'B': 1,
                     'K': 1024,
                     'M': 1048576,
                     'G': 1073741824,
                     'T': 1099511627776
                     }
            if human.has_key(value[-1]):
                value = int(value[:-1]) * human[value[-1]]
        except Exception:
            logging.warn("cg.set_prop() fallback into cg.set_property.")
            value = _value
        self.set_property(prop, value, pwd, check, checkprop)

    def set_property(self, prop, value, pwd=None, check=True, checkprop=None):
        """
        Sets the property value
        :param prop: property name (file)
        :param value: desired value
        :param pwd: cgroup directory
        :param check: check the value after setup / override checking value
        :param checkprop: override prop when checking the value
        """
        value = str(value)
        if pwd is None:
            pwd = self.root
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            open(os.path.join(pwd, prop), 'w').write(value)
        except Exception, inst:
            raise error.TestError("cg.set_property(): %s" % inst)

        if check is not False:
            if check is True:
                check = value
            if checkprop is None:
                checkprop = prop
            _values = self.get_property(checkprop, pwd)
            # Sanitize non printable characters before check
            check = " ".join(check.split())
            if check not in _values:
                raise error.TestError("cg.set_property(): Setting failed: "
                                      "desired = %s, real values = %s"
                                      % (repr(check), repr(_values)))

    def cgset_property(self, prop, value, pwd=None, check=True, checkprop=None):
        """
        Sets the property value by cgset command

        :param: prop: property name (file)
        :param: value: desired value
        :param pwd: cgroup directory
        :param check: check the value after setup / override checking value
        :param checkprop: override prop when checking the value
        """
        if pwd is None:
            pwd = self.root
        if isinstance(pwd, int):
            pwd = self.cgroups[pwd]
        try:
            cgroup = self.get_cgroup_name(pwd)
            cgset_cmd = "cgset -r %s='%s' %s" % (prop, value, cgroup)
            utils.run(cgset_cmd, ignore_status=False)
        except error.CmdError, detail:
            raise error.TestFail("Modify %s failed!:\n%s" % (prop, detail))

        if check is not False:
            if check is True:
                check = value
            if checkprop is None:
                checkprop = prop
            _values = self.get_property(checkprop,
                                        self.get_cgroup_index(cgroup))
            # Sanitize non printable characters before check
            check = " ".join(check.split())
            if check not in _values:
                raise error.TestError("cg.set_property(): Setting failed: "
                                      "desired = %s, real values = %s"
                                      % (repr(check), repr(_values)))

    def smoke_test(self):
        """
        Smoke test
        Module independent basic tests
        """
        pwd = self.mk_cgroup()

        ps = self.test("smoke")
        if ps is None:
            raise error.TestError("cg.smoke_test: Couldn't create process")

        if (ps.poll() is not None):
            raise error.TestError("cg.smoke_test: Process died unexpectidly")

        # New process should be a root member
        if self.is_root_cgroup(ps.pid):
            raise error.TestError("cg.smoke_test: Process is not a root member")

        # Change the cgroup
        self.set_cgroup(ps.pid, pwd)

        # Try to remove used cgroup
        try:
            self.rm_cgroup(pwd)
        except error.TestError:
            pass
        else:
            raise error.TestError("cg.smoke_test: Unexpected successful"
                                  " deletion of the used cgroup")

        # Return the process into the root cgroup
        self.set_root_cgroup(ps.pid)

        # It should be safe to remove the cgroup now
        self.rm_cgroup(pwd)

        # Finish the process
        ps.stdin.write('\n')
        time.sleep(2)
        if (ps.poll() is None):
            raise error.TestError("cg.smoke_test: Process is not finished")


class CgroupModules(object):

    """
    Handles the list of different cgroup filesystems.
    """

    def __init__(self, mountdir=None):
        self.modules = []
        self.modules.append([])
        self.modules.append([])
        self.modules.append([])
        if mountdir is None:
            self.mountdir = mkdtemp(prefix='cgroup-') + '/'
            self.rm_mountdir = True
        else:
            self.mountdir = mountdir
            self.rm_mountdir = False

    def __del__(self):
        """
        Unmount all cgroups and remove the mountdir
        """
        for i in range(len(self.modules[0])):
            if self.modules[2][i]:
                try:
                    utils.system('umount %s -l' % self.modules[1][i])
                except Exception, failure_detail:
                    logging.warn("CGM: Couldn't unmount %s directory: %s",
                                 self.modules[1][i], failure_detail)
        try:
            if self.rm_mountdir:
                # If delete /cgroup/, this action will break cgroup service.
                shutil.rmtree(self.mountdir)
        except Exception:
            logging.warn("CGM: Couldn't remove the %s directory", self.mountdir)

    def init(self, _modules):
        """
        Checks the mounted modules and if necessary mounts them into tmp
            mountdir.
        :param _modules: Desired modules.'memory','cpu,cpuset'...
        :return: Number of initialized modules.
        """
        logging.debug("Desired cgroup modules: %s", _modules)
        mounts = []
        proc_mounts = open('/proc/mounts', 'r')
        line = proc_mounts.readline().split()
        while line:
            if line[2] == 'cgroup':
                mounts.append(line)
            line = proc_mounts.readline().split()
        proc_mounts.close()

        for module in _modules:
            # Is it already mounted?
            i = False
            _module = set(module.split(','))
            for mount in mounts:
                # 'memory' or 'memory,cpuset'
                if _module.issubset(mount[3].split(',')):
                    self.modules[0].append(module)
                    self.modules[1].append(mount[1])
                    self.modules[2].append(False)
                    i = True
                    break
            if not i:
                # Not yet mounted
                module_path = os.path.join(self.mountdir, module)
                if not os.path.exists(module_path):
                    os.mkdir(module_path)
                cmd = ('mount -t cgroup -o %s %s %s' %
                       (module, module, module_path))
                try:
                    utils.run(cmd)
                    self.modules[0].append(module)
                    self.modules[1].append(module_path)
                    self.modules[2].append(True)
                except error.CmdError:
                    logging.info("Cgroup module '%s' not available", module)

        logging.debug("Initialized cgroup modules: %s", self.modules[0])
        return len(self.modules[0])

    def get_pwd(self, module):
        """
        Returns the mount directory of 'module'
        :param module: desired module (memory, ...)
        :return: mount directory of 'module' or None
        """
        try:
            i = self.modules[0].index(module)
        except Exception, inst:
            logging.error("module %s not found: %s", module, inst)
            return None
        return self.modules[1][i]


def get_load_per_cpu(_stats=None):
    """
    Gather load per cpu from /proc/stat
    :param _stats: previous values
    :return: list of diff/absolute values of CPU times [SUM, CPU1, CPU2, ...]
    """
    stats = []
    f_stat = open('/proc/stat', 'r')
    if _stats:
        for i in range(len(_stats)):
            stats.append(int(f_stat.readline().split()[1]) - _stats[i])
    else:
        line = f_stat.readline()
        while line:
            if line.startswith('cpu'):
                stats.append(int(line.split()[1]))
            else:
                break
            line = f_stat.readline()
    return stats


def get_cgroup_mountpoint(controller):
    """
    Get desired controller's mountpoint

    @controller: Desired controller
    :return: controller's mountpoint
    """
    if controller not in get_all_controllers():
        raise error.TestError("Doesn't support controller <%s>" % controller)
    f_cgcon = open("/proc/mounts", "rU")
    cgconf_txt = f_cgcon.read()
    f_cgcon.close()
    mntpt = re.findall(r"\s(\S*cgroup/\S*,*%s,*\S*)" % controller, cgconf_txt)
    return mntpt[0]


def get_all_controllers():
    """
    Get all controllers used in system

    :return: all used controllers(controller_list)
    """
    try:
        result = utils.run("lssubsys", ignore_status=False)
        controllers_str = result.stdout.strip()
        controller_list = []
        for controller in controllers_str.splitlines():
            controller_sub_list = controller.split(",")
            controller_list += controller_sub_list
    except error.CmdError:
        controller_list = ['cpuacct', 'cpu', 'memory', 'cpuset',
                           'devices', 'freezer', 'blkio', 'netcls']
    return controller_list


def resolve_task_cgroup_path(pid, controller):
    """
    Resolving cgroup mount path of a particular task

    :params: pid : process id of a task for which the cgroup path required
    :params: controller: takes one of the controller names in controller list

    :return: resolved path for cgroup controllers of a given pid
    """
    if controller not in get_all_controllers():
        raise error.TestError("Doesn't support controller <%s>" % controller)
    root_path = get_cgroup_mountpoint(controller)

    proc_cgroup = "/proc/%d/cgroup" % pid
    if not os.path.isfile(proc_cgroup):
        raise NameError('File %s does not exist\n Check whether cgroup \
                                    installed in the system' % proc_cgroup)

    try:
        proc_file = open(proc_cgroup, 'r')
        proc_cgroup_txt = proc_file.read()
    finally:
        proc_file.close()

    mount_path = re.findall(r":\S*,*%s,*\S*:(\S*)\n" % controller, proc_cgroup_txt)
    return os.path.join(root_path, mount_path[0].strip("/"))


def service_cgconfig_control(action):
    """
    Cgconfig control by action.

    If cmd executes successfully, return True, otherwise return False.
    If the action is status, return True when it's running, otherwise return
    False. To check if the cgconfig stuff is available, use action "exists".

    @ param action: start|stop|status|restart|condrestart
    """
    actions = ['start', 'stop', 'restart', 'condrestart']
    if action in actions:
        try:
            utils.run("service cgconfig %s" % action)
            logging.debug("%s cgconfig successfully", action)
            return True
        except error.CmdError, detail:
            logging.error("Failed to %s cgconfig:\n%s", action, detail)
            return False
    elif action == "status" or action == "exists":
        cmd_result = utils.run("service cgconfig status", ignore_status=True)
        if action == "exists":
            if cmd_result.exit_status:
                return False
            else:
                return True

        if (not cmd_result.exit_status and
                cmd_result.stdout.strip()) == "Running":
            logging.info("Cgconfig service is running")
            return True
        else:
            return False
    else:
        raise error.TestError("Unknown action: %s" % action)


# Split cgconfig action function, it will be more clear.
def cgconfig_start():
    """
    Stop cgconfig service
    """
    return service_cgconfig_control("start")


def cgconfig_stop():
    """
    Start cgconfig service
    """
    return service_cgconfig_control("stop")


def cgconfig_restart():
    """
    Restart cgconfig service
    """
    return service_cgconfig_control("restart")


def cgconfig_condrestart():
    """
    Condrestart cgconfig service
    """
    return service_cgconfig_control("condrestart")


def cgconfig_is_running():
    """
    Check cgconfig service status
    """
    return service_cgconfig_control("status")


def cgconfig_exists():
    """
    Check if cgconfig is available on the host or perhaps systemd is used
    """
    return service_cgconfig_control("exists")


def all_cgroup_delete():
    """
    Clear all cgroups in system
    """
    try:
        utils.run("cgclear", ignore_status=False)
    except error.CmdError, detail:
        logging.warn("cgclear: Fail to clear all cgroups, some specific system"
                     " cgroups might exist and affect further testing.")
