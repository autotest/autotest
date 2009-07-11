#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Bootloader class.

        Bootloader: a program to boot Kernels on a Host.
"""

import os, sys, weakref
from autotest_lib.client.common_lib import error
from autotest_lib.server import utils

BOOTTOOL_SRC = '../client/tools/boottool'  # Get it from autotest client


class Bootloader(object):
    """
    This class represents a bootloader.

    It can be used to add a kernel to the list of kernels that can be
    booted by a bootloader. It can also make sure that this kernel will
    be the one chosen at next reboot.
    """

    def __init__(self, host, xen_mode=False):
        super(Bootloader, self).__init__()
        self._host = weakref.ref(host)
        self._boottool_path = None
        self.xen_mode = xen_mode


    def get_type(self):
        return self._run_boottool('--bootloader-probe').stdout.strip()


    def get_architecture(self):
        return self._run_boottool('--arch-probe').stdout.strip()


    def get_titles(self):
        return self._run_boottool('--info all | grep title | '
                'cut -d " " -f2-').stdout.strip().split('\n')


    def get_default_title(self):
        default = int(self.get_default())
        return self.get_titles()[default]


    def get_default(self):
        return self._run_boottool('--default').stdout.strip()


    def _get_info(self, info_id):
        retval = self._run_boottool('--info=%s' % info_id).stdout

        results = []
        info = {}
        for line in retval.splitlines():
            if not line.strip():
                if info:
                    results.append(info)
                    info = {}
            else:
                key, val = line.split(":", 1)
                info[key.strip()] = val.strip()
        if info:
            results.append(info)

        return results


    def get_info(self, index):
        results = self._get_info(index)
        if results:
            return results[0]
        else:
            return {}


    def get_all_info(self):
        return self._get_info('all')


    def set_default(self, index):
        assert(index is not None)
        if self._host().job:
            self._host().job.last_boot_tag = None
        self._run_boottool('--set-default=%s' % index)


    # 'kernel' can be a position number or a title
    def add_args(self, kernel, args):
        parameters = '--update-kernel=%s --args="%s"' % (kernel, args)

        #add parameter if this is a Xen entry
        if self.xen_mode:
            parameters += ' --xen'

        self._run_boottool(parameters)


    def add_xen_hypervisor_args(self, kernel, args):
        self._run_boottool('--xen --update-xenhyper=%s --xha="%s"' \
                            % (kernel, args))


    def remove_args(self, kernel, args):
        params = '--update-kernel=%s --remove-args="%s"' % (kernel, args)

        #add parameter if this is a Xen entry
        if self.xen_mode:
            params += ' --xen'

        self._run_boottool(params)


    def remove_xen_hypervisor_args(self, kernel, args):
        self._run_boottool('--xen --update-xenhyper=%s '
                '--remove-args="%s"') % (kernel, args)


    def add_kernel(self, path, title='autoserv', root=None, args=None,
            initrd=None, xen_hypervisor=None, default=True):
        """
        If an entry with the same title is already present, it will be
        replaced.
        """
        if title in self.get_titles():
            self._run_boottool('--remove-kernel "%s"' % (
                    utils.sh_escape(title),))

        parameters = '--add-kernel "%s" --title "%s"' % (
                utils.sh_escape(path), utils.sh_escape(title),)

        if root:
            parameters += ' --root "%s"' % (utils.sh_escape(root),)

        if args:
            parameters += ' --args "%s"' % (utils.sh_escape(args),)

        # add an initrd now or forever hold your peace
        if initrd:
            parameters += ' --initrd "%s"' % (
                    utils.sh_escape(initrd),)

        if default:
            parameters += ' --make-default'

        # add parameter if this is a Xen entry
        if self.xen_mode:
            parameters += ' --xen'
            if xen_hypervisor:
                parameters += ' --xenhyper "%s"' % (
                        utils.sh_escape(xen_hypervisor),)

        self._run_boottool(parameters)


    def remove_kernel(self, kernel):
        self._run_boottool('--remove-kernel=%s' % kernel)


    def boot_once(self, title):
        if self._host().job:
            self._host().job.last_boot_tag = title
        if not title:
            title = self.get_default_title()
        self._run_boottool('--boot-once --title=%s' % title)


    def install_boottool(self):
        if self._host() is None:
            raise error.AutoservError(
                "Host does not exist anymore")
        tmpdir = self._host().get_tmp_dir()
        self._host().send_file(os.path.abspath(os.path.join(
                utils.get_server_dir(), BOOTTOOL_SRC)), tmpdir)
        self._boottool_path= os.path.join(tmpdir,
                os.path.basename(BOOTTOOL_SRC))


    def _get_boottool_path(self):
        if not self._boottool_path:
            self.install_boottool()
        return self._boottool_path


    def _set_boottool_path(self, path):
        self._boottool_path = path


    boottool_path = property(_get_boottool_path, _set_boottool_path)


    def _run_boottool(self, cmd):
        return self._host().run(self.boottool_path + ' ' + cmd)
