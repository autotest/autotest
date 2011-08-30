#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Helpers for cgroup testing.

@copyright: 2011 Red Hat Inc.
@author: Lukas Doktor <ldoktor@redhat.com>
"""
import os, logging, subprocess, time, shutil
from tempfile import mkdtemp
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


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


    def initialize(self, modules):
        """
        Initializes object for use.

        @param modules: Array of all available cgroup modules.
        @return: 0 when PASSED.
        """
        self.root = modules.get_pwd(self.module)
        if self.root:
            return 0
        else:
            logging.error("cg.initialize(): Module %s not found", self.module)
            return -1
        return 0


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
            logging.error("cg.mk_cgroup(): %s" , inst)
            return None
        return pwd


    def rm_cgroup(self, pwd, supress=False):
        """
        Removes cgroup.

        @param pwd: cgroup directory.
        @param supress: supress output.
        @return: 0 when PASSED
        """
        try:
            os.rmdir(pwd)
        except Exception, inst:
            if not supress:
                logging.error("cg.rm_cgroup(): %s" , inst)
            return -1
        return 0


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
        @return: 0 when PASSED
        """
        try:
            open(pwd+'/tasks', 'w').write(str(pid))
        except Exception, inst:
            logging.error("cg.set_cgroup(): %s" , inst)
            return -1
        if self.is_cgroup(pid, pwd):
            logging.error("cg.set_cgroup(): Setting %d pid into %s cgroup "
                          "failed", pid, pwd)
            return -1
        else:
            return 0

    def set_root_cgroup(self, pid):
        """
        Resets the cgroup membership (sets to root)
        @param pid: pid of the process
        @return: 0 when PASSED
        """
        return self.set_cgroup(pid, self.root)


    def get_prop(self, prop, pwd=None, supress=False):
        """
        Gets one line of the property value
        @param prop: property name (file)
        @param pwd: cgroup directory
        @param supress: supress the output
        @return: String value or None when FAILED
        """
        tmp = self.get_property(prop, pwd, supress)
        if tmp:
            if tmp[0][-1] == '\n':
                tmp[0] = tmp[0][:-1]
            return tmp[0]
        else:
            return None


    def get_property(self, prop, pwd=None, supress=False):
        """
        Gets the property value
        @param prop: property name (file)
        @param pwd: cgroup directory
        @param supress: supress the output
        @return: [] values or None when FAILED
        """
        if pwd == None:
            pwd = self.root
        try:
            ret = open(pwd+prop, 'r').readlines()
        except Exception, inst:
            ret = None
            if not supress:
                logging.error("cg.get_property(): %s" , inst)
        return ret


    def set_prop(self, prop, value, pwd=None, check=True):
        """
        Sets the one-line property value concerning the K,M,G postfix
        @param prop: property name (file)
        @param value: desired value
        @param pwd: cgroup directory
        @param check: check the value after setup
        @return: 0 when PASSED
        """
        _value = value
        try:
            value = str(value)
            if value[-1] == '\n':
                value = value[:-1]
            if value[-1] == 'K':
                value = int(value[:-1]) * 1024
            elif value[-1] == 'M':
                value = int(value[:-1]) * 1048576
            elif value[-1] == 'G':
                value = int(value[:-1]) * 1073741824
        except:
            logging.error("cg.set_prop() fallback into cg.set_property.")
            value = _value
        return self.set_property(prop, value, pwd, check)


    def set_property(self, prop, value, pwd=None, check=True):
        """
        Sets the property value
        @param prop: property name (file)
        @param value: desired value
        @param pwd: cgroup directory
        @param check: check the value after setup
        @return: 0 when PASSED
        """
        value = str(value)
        if pwd == None:
            pwd = self.root
        try:
            open(pwd+prop, 'w').write(value)
        except Exception, inst:
            logging.error("cg.set_property(): %s" , inst)
            return -1
        if check:
            # Get the first line - '\n'
            _value = self.get_property(prop, pwd)[0][:-1]
            if value != _value:
                logging.error("cg.set_property(): Setting failed: desired = %s,"
                              " real value = %s", value, _value)
                return -1
        return 0


    def smoke_test(self):
        """
        Smoke test
        Module independent basic tests
        """
        part = 0
        pwd = self.mk_cgroup()
        if pwd == None:
            logging.error("cg.smoke_test[%d]: Can't create cgroup", part)
            return -1

        part += 1
        ps = self.test("smoke")
        if ps == None:
            logging.error("cg.smoke_test[%d]: Couldn't create process", part)
            return -1

        part += 1
        if (ps.poll() != None):
            logging.error("cg.smoke_test[%d]: Process died unexpectidly", part)
            return -1

        # New process should be a root member
        part += 1
        if self.is_root_cgroup(ps.pid):
            logging.error("cg.smoke_test[%d]: Process is not a root member",
                          part)
            return -1

        # Change the cgroup
        part += 1
        if self.set_cgroup(ps.pid, pwd):
            logging.error("cg.smoke_test[%d]: Could not set cgroup", part)
            return -1

        # Try to remove used cgroup
        part += 1
        if self.rm_cgroup(pwd, supress=True) == 0:
            logging.error("cg.smoke_test[%d]: Unexpected successful deletion of"
                          " the used cgroup", part)
            return -1

        # Return the process into the root cgroup
        part += 1
        if self.set_root_cgroup(ps.pid):
            logging.error("cg.smoke_test[%d]: Could not return the root cgroup "
                          "membership", part)
            return -1

        # It should be safe to remove the cgroup now
        part += 1
        if self.rm_cgroup(pwd):
            logging.error("cg.smoke_test[%d]: Can't remove cgroup directory",
                          part)
            return -1

        # Finish the process
        part += 1
        ps.stdin.write('\n')
        time.sleep(2)
        if (ps.poll() == None):
            logging.error("cg.smoke_test[%d]: Process is not finished", part)
            return -1

        return 0


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


    def init(self, _modules):
        """
        Checks the mounted modules and if necessary mounts them into tmp
            mountdir.
        @param _modules: Desired modules.
        @return: Number of initialized modules.
        """
        logging.debug("Desired cgroup modules: %s", _modules)
        mounts = []
        fp = open('/proc/mounts', 'r')
        line = fp.readline().split()
        while line:
            if line[2] == 'cgroup':
                mounts.append(line)
            line = fp.readline().split()
        fp.close()

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


    def cleanup(self):
        """
        Unmount all cgroups and remove the mountdir.
        """
        for i in range(len(self.modules[0])):
            if self.modules[2][i]:
                utils.system('umount %s -l' % self.modules[1][i],
                             ignore_status=True)
        shutil.rmtree(self.mountdir)


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
