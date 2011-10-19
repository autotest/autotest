#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Helpers for cgroup testing.

@copyright: 2011 Red Hat Inc.
@author: Lukas Doktor <ldoktor@redhat.com>
"""
import logging, os, shutil, subprocess, time, traceback
from tempfile import mkdtemp
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

def _traceback(name, exc_info):
    """
    Formats traceback into lines "name: line\nname: line"
    @param name: desired line preposition
    @param exc_info: sys.exc_info of the exception
    @return: string which contains beautifully formatted exception
    """
    out = "\n"
    for line in traceback.format_exception(exc_info[0], exc_info[1],
                                           exc_info[2]):
        out += "%s: %s" % (name, line)
    return out


class Cgroup(object):
    """
    Cgroup handling class.
    """
    def __init__(self, module, _client):
        """
        Constructor
        @param module: Name of the cgroup module
        @param _client: Test script pwd + name
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

        @param modules: Array of all available cgroup modules.
        """
        self.root = modules.get_pwd(self.module)
        if not self.root:
            raise error.TestError("cg.initialize(): Module %s not found"
                                                                % self.module)


    def mk_cgroup(self, root=None):
        """
        Creates new temporary cgroup
        @param root: where to create this cgroup (default: self.root)
        @return: 0 when PASSED
        """
        try:
            if root:
                pwd = mkdtemp(prefix='cgroup-', dir=root) + '/'
            else:
                pwd = mkdtemp(prefix='cgroup-', dir=self.root) + '/'
        except Exception, inst:
            raise error.TestError("cg.mk_cgroup(): %s" % inst)
        self.cgroups.append(pwd)
        return pwd


    def rm_cgroup(self, pwd):
        """
        Removes cgroup.

        @param pwd: cgroup directory.
        """
        try:
            os.rmdir(pwd)
            self.cgroups.remove(pwd)
        except ValueError:
            logging.warn("cg.rm_cgroup(): Removed cgroup which wasn't created"
                         "using this Cgroup")
        except Exception, inst:
            raise error.TestError("cg.rm_cgroup(): %s" % inst)


    def test(self, cmd):
        """
        Executes cgroup_client.py with cmd parameter.

        @param cmd: command to be executed
        @return: subprocess.Popen() process
        """
        logging.debug("cg.test(): executing paralel process '%s'", cmd)
        cmd = self._client + ' ' + cmd
        process = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, close_fds=True)
        return process


    def is_cgroup(self, pid, pwd):
        """
        Checks if the 'pid' process is in 'pwd' cgroup
        @param pid: pid of the process
        @param pwd: cgroup directory
        @return: 0 when is 'pwd' member
        """
        if open(pwd + '/tasks').readlines().count("%d\n" % pid) > 0:
            return 0
        else:
            return -1


    def is_root_cgroup(self, pid):
        """
        Checks if the 'pid' process is in root cgroup (WO cgroup)
        @param pid: pid of the process
        @return: 0 when is 'root' member
        """
        return self.is_cgroup(pid, self.root)


    def set_cgroup(self, pid, pwd):
        """
        Sets cgroup membership
        @param pid: pid of the process
        @param pwd: cgroup directory
        """
        try:
            open(pwd+'/tasks', 'w').write(str(pid))
        except Exception, inst:
            raise error.TestError("cg.set_cgroup(): %s" % inst)
        if self.is_cgroup(pid, pwd):
            raise error.TestError("cg.set_cgroup(): Setting %d pid into %s "
                                 "cgroup failed" % (pid, pwd))

    def set_root_cgroup(self, pid):
        """
        Resets the cgroup membership (sets to root)
        @param pid: pid of the process
        @return: 0 when PASSED
        """
        return self.set_cgroup(pid, self.root)


    def get_property(self, prop, pwd=None):
        """
        Gets the property value
        @param prop: property name (file)
        @param pwd: cgroup directory
        @return: [] values or None when FAILED
        """
        if pwd == None:
            pwd = self.root
        try:
            # Remove tailing '\n' from each line
            ret = [_[:-1] for _ in open(pwd+prop, 'r').readlines()]
            if ret:
                return ret
            else:
                return [""]
        except Exception, inst:
            raise error.TestError("cg.get_property(): %s" % inst)


    def set_property_h(self, prop, value, pwd=None, check=True, checkprop=None):
        """
        Sets the one-line property value concerning the K,M,G postfix
        @param prop: property name (file)
        @param value: desired value
        @param pwd: cgroup directory
        @param check: check the value after setup / override checking value
        @param checkprop: override prop when checking the value
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
        @param prop: property name (file)
        @param value: desired value
        @param pwd: cgroup directory
        @param check: check the value after setup / override checking value
        @param checkprop: override prop when checking the value
        """
        value = str(value)
        if pwd == None:
            pwd = self.root
        try:
            open(pwd+prop, 'w').write(value)
        except Exception, inst:
            raise error.TestError("cg.set_property(): %s" % inst)
        if check != False:
            if check == True:
                check = value
            if checkprop == None:
                checkprop = prop
            _values = self.get_property(checkprop, pwd)
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
        if ps == None:
            raise error.TestError("cg.smoke_test: Couldn't create process")

        if (ps.poll() != None):
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
            raise error.TestError("cg.smoke_test: Unexpected successful deletion"
                                 " of the used cgroup")

        # Return the process into the root cgroup
        self.set_root_cgroup(ps.pid)

        # It should be safe to remove the cgroup now
        self.rm_cgroup(pwd)

        # Finish the process
        ps.stdin.write('\n')
        time.sleep(2)
        if (ps.poll() == None):
            raise error.TestError("cg.smoke_test: Process is not finished")


class CgroupModules(object):
    """
    Handles the list of different cgroup filesystems.
    """
    def __init__(self):
        self.modules = []
        self.modules.append([])
        self.modules.append([])
        self.modules.append([])
        self.mountdir = mkdtemp(prefix='cgroup-') + '/'

    def __del__(self):
        """
        Unmount all cgroups and remove the mountdir
        """
        for i in range(len(self.modules[0])):
            if self.modules[2][i]:
                try:
                    utils.system('umount %s -l' % self.modules[1][i])
                except Exception, failure_detail:
                    logging.warn("CGM: Couldn't unmount %s directory: %s"
                                 % (self.modules[1][i], failure_detail))
        try:
            shutil.rmtree(self.mountdir)
        except Exception:
            logging.warn("CGM: Couldn't remove the %s directory", self.mountdir)

    def init(self, _modules):
        """
        Checks the mounted modules and if necessary mounts them into tmp
            mountdir.
        @param _modules: Desired modules.
        @return: Number of initialized modules.
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
            for mount in mounts:
                if mount[3].find(module) != -1:
                    self.modules[0].append(module)
                    self.modules[1].append(mount[1] + '/')
                    self.modules[2].append(False)
                    i = True
                    break
            if not i:
                # Not yet mounted
                os.mkdir(self.mountdir + module)
                cmd = ('mount -t cgroup -o %s %s %s' %
                       (module, module, self.mountdir + module))
                try:
                    utils.run(cmd)
                    self.modules[0].append(module)
                    self.modules[1].append(self.mountdir + module)
                    self.modules[2].append(True)
                except error.CmdError:
                    logging.info("Cgroup module '%s' not available", module)

        logging.debug("Initialized cgroup modules: %s", self.modules[0])
        return len(self.modules[0])


    def get_pwd(self, module):
        """
        Returns the mount directory of 'module'
        @param module: desired module (memory, ...)
        @return: mount directory of 'module' or None
        """
        try:
            i = self.modules[0].index(module)
        except Exception, inst:
            logging.error("module %s not found: %s", module, inst)
            return None
        return self.modules[1][i]
