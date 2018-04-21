#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Bootloader class.

        Bootloader: a program to boot Kernels on a Host.
"""

import imp
import os
import sys
import weakref

from autotest.client.shared import error
from autotest.server import utils

#
# This performs some import magic, to import the boottool cli as a module
#
CURRENT_DIRECTORY = os.path.dirname(sys.modules[__name__].__file__)
CLIENT_DIRECTORY = os.path.abspath(os.path.join(CURRENT_DIRECTORY,
                                                "..", "..", "client"))
BOOTTOOL_CLI_PATH = os.path.join(CLIENT_DIRECTORY, "tools", "boottool.py")
imp.load_source("boottool_cli", BOOTTOOL_CLI_PATH)
from boottool_cli import parse_entry


class Bootloader(object):

    """
    This class gives access to a host's bootloader services.

    It can be used to add a kernel to the list of kernels that can be
    booted by a bootloader. It can also make sure that this kernel will
    be the one chosen at next reboot.
    """

    def __init__(self, host):
        '''
        Instantiates a new bootloader object
        '''
        self._host = weakref.ref(host)
        self._boottool_path = None
        self.bootloader = None

    def _install_boottool(self):
        '''
        Installs boottool on the host
        '''
        if self._host() is None:
            raise error.AutoservError(
                "Host does not exist anymore")
        tmpdir = self._host().get_tmp_dir()
        self._host().send_file(os.path.abspath(os.path.join(
            utils.get_server_dir(), BOOTTOOL_CLI_PATH)), tmpdir)
        self._boottool_path = os.path.join(tmpdir,
                                           os.path.basename(BOOTTOOL_CLI_PATH))

    def _get_boottool_path(self):
        '''
        Returns the boottool path, installing it if necessary
        '''
        if not self._boottool_path:
            self._install_boottool()
        return self._boottool_path

    def _set_bootloader(self):
        '''
        Attempts to detect what bootloader is installed on the system

        The result of this method is used in all other calls to grubby,
        so that it acts accordingly to the bootloader detected.
        '''
        result = self.get_bootloader()
        if result is not None:
            self.bootloader = result

    def _run_boottool_cmd(self, *options):
        '''
        Runs a boottool command, escaping parameters
        '''
        cmd = self._get_boottool_path()
        # FIXME: add unsafe options strings sequence to host.run() parameters
        for option in options:
            cmd += ' "%s"' % utils.sh_escape(option)
        return self._host().run(cmd)

    def _run_boottool_stdout(self, *options):
        '''
        Runs a boottool command, return its output
        '''
        return self._run_boottool_cmd(*options).stdout

    def _run_boottool_exit_status(self, *options):
        '''
        Runs a boottool command, return its exit status
        '''
        return self._run_boottool_cmd(*options).exit_status

    def get_bootloader(self):
        """
        Get the bootloader name that is detected on this machine

        :return: name of detected bootloader
        """
        return self._run_boottool_stdout('--bootloader-probe').strip()

    get_type = get_bootloader

    def get_architecture(self):
        '''
        Get the system architecture
        '''
        return self._run_boottool_stdout('--arch-probe').strip()

    arch_probe = get_architecture

    def get_titles(self):
        """
        Returns a list of boot entries titles.
        """
        return [entry.get('title', '')
                for entry in self.get_entries().values()]

    def get_default_index(self):
        """
        Return an int with the # of the default bootloader entry.
        """
        return int(self._run_boottool_stdout('--default').strip())

    get_default = get_default_index

    def set_default_by_index(self, index):
        '''
        Sets the given entry number to be the default on every next boot

        To set a default only for the next boot, use boot_once() instead.

        :param index: entry index number to set as the default.
        '''
        if self._host().job:
            self._host().job.last_boot_tag = None
        return self._run_boottool_exit_status('--set-default=%s' %
                                              utils.sh_escape(str(index)))

    set_default = set_default_by_index

    def get_default_title(self):
        '''
        Get the default entry title.

        :return: a string of the default entry title.
        '''
        default = self.get_default_index()
        entry = self.get_entry(default)
        if entry.has_key('title'):
            return entry['title']
        elif 'label' in entry:
            return entry['label']

    def get_entry(self, entry):
        """
        Get a single bootloader entry information.

        :param entry: entry index
        :return: a dictionary of key->value where key is the type of entry
                information (ex. 'title', 'args', 'kernel', etc) and value
                is the value for that piece of information.
        """
        output = self._run_boottool_stdout('--info=%s' % entry).strip()
        return parse_entry(output, ":")

    def get_entries(self):
        """
        Get all entries information.

        :return: a dictionary of index -> entry where entry is a dictionary
                of entry information as described for get_entry().
        """
        raw = "\n" + self._run_boottool_stdout('--info=all')
        entries = {}
        for entry_str in raw.split("\nindex"):
            if len(entry_str.strip()) == 0:
                continue
            entry = parse_entry("index" + entry_str, ":")
            entries[entry["index"]] = entry

        return entries

    def add_args(self, kernel, args):
        """
        Add cmdline arguments for the specified kernel.

        :param kernel: can be a position number (index) or title
        :param args: argument to be added to the current list of args
        """
        return self._run_boottool_exit_status('--update-kernel=%s' %
                                              utils.sh_escape(str(kernel)),
                                              '--args=%s' %
                                              utils.sh_escape(args))

    def remove_args(self, kernel, args):
        """
        Removes specified cmdline arguments.

        :param kernel: can be a position number (index) or title
        :param args: argument to be removed of the current list of args
        """
        return self._run_boottool_exit_status('--update-kernel=%s' %
                                              utils.sh_escape(str(kernel)),
                                              '--remove-args=%s' %
                                              utils.sh_escape(args))

    def add_kernel(self, path, title='autoserv', root=None, args=None,
                   initrd=None, default=False, position='end'):
        """
        Add a kernel entry to the bootloader (or replace if one exists
        already with the same title).

        :param path: string path to the kernel image file
        :param title: title of this entry in the bootloader config
        :param root: string of the root device
        :param args: string with cmdline args
        :param initrd: string path to the initrd file
        :param default: set to True to make this entry the default one
                (default False)
        :param position: where to insert the new entry in the bootloader
                config file (default 'end', other valid input 'start', or
                # of the title)
        """
        parameters = ['--add-kernel=%s' % path, '--title=%s' % title]

        if args:
            parameters.append('--args=%s' % args)

        if initrd:
            parameters.append('--initrd=%s' % initrd)

        if default:
            parameters.append('--make-default')

        return self._run_boottool_exit_status(parameters)

    def remove_kernel(self, kernel):
        parameters = ['--remove-kernel=%s' % kernel]
        return self._run_boottool_exit_status(parameters)

    def boot_once(self, title):
        if self._host().job:
            self._host().job.last_boot_tag = title

        title_opt = '--title=%s' % utils.sh_escape(title)
        return self._run_boottool_exit_status('--boot-once',
                                              title_opt)
