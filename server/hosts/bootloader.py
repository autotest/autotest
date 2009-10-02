#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Bootloader class.

        Bootloader: a program to boot Kernels on a Host.
"""

import os, weakref
from autotest_lib.client.common_lib import error, boottool
from autotest_lib.server import utils

BOOTTOOL_SRC = '../client/tools/boottool'  # Get it from autotest client


class Bootloader(boottool.boottool):
    """
    This class gives access to a host's bootloader services.

    It can be used to add a kernel to the list of kernels that can be
    booted by a bootloader. It can also make sure that this kernel will
    be the one chosen at next reboot.
    """

    def __init__(self, host):
        super(Bootloader, self).__init__()
        self._host = weakref.ref(host)
        self._boottool_path = None


    def set_default(self, index):
        if self._host().job:
            self._host().job.last_boot_tag = None
        super(Bootloader, self).set_default(index)


    def boot_once(self, title):
        if self._host().job:
            self._host().job.last_boot_tag = title

        super(Bootloader, self).boot_once(title)


    def _install_boottool(self):
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
            self._install_boottool()
        return self._boottool_path


    def _run_boottool(self, *options):
        cmd = self._get_boottool_path()
        # FIXME: add unsafe options strings sequence to host.run() parameters
        for option in options:
            cmd += ' "%s"' % utils.sh_escape(option)
        return self._host().run(cmd).stdout
