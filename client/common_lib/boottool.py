# Copyright 2009 Google Inc. Released under the GPL v2

import re


class boottool(object):
    """
    Common class for the client and server side boottool wrappers.
    """

    def __init__(self):
        self._xen_mode = False


    def _run_boottool(self, *options):
        """
        Override in derivations to execute the "boottool" command and return
        the stdout output in case of success. In case of failure an exception
        should be raised.

        @param options: a sequence of command line arguments to give to the
                boottool command
        @return string with the stdout output of the boottool command.
        @raise Exception in case of boottool command failure.
        """
        raise NotImplementedError('_run_boottool not implemented!')


    def get_type(self):
        """
        Return the installed bootloader type.
        """
        return self._run_boottool('--bootloader-probe').strip()


    def get_architecture(self):
        """
        Get the system architecture reported by the bootloader.
        """
        return self._run_boottool('--arch-probe').strip()


    def get_titles(self):
        """
        Returns a list of boot entries titles.
        """
        return [entry['title'] for entry in self.get_entries().itervalues()]


    def get_default(self):
        """
        Return an int with the # of the default bootloader entry.
        """
        return int(self._run_boottool('--default').strip())


    def set_default(self, index):
        """
        Set the default boot entry.

        @param index: entry index number to set as the default.
        """
        assert index is not None
        self._run_boottool('--set-default=%s' % index)


    def get_default_title(self):
        """
        Get the default entry title.

        @return a string of the default entry title.
        """
        return self.get_entry('default')['title']


    def _parse_entry(self, entry_str):
        """
        Parse entry as returned by boottool.

        @param entry_str: one entry information as returned by boottool
        @return: dictionary of key -> value where key is the string before
                the first ":" in an entry line and value is the string after
                it
        """
        entry = {}
        for line in entry_str.splitlines():
            if len(line) == 0:
                continue
            name, value = line.split(':', 1)
            name = name.strip()
            value = value.strip()

            if name == 'index':
                # index values are integrals
                value = int(value)
            entry[name] = value

        return entry


    def get_entry(self, search_info):
        """
        Get a single bootloader entry information.

        NOTE: if entry is "fallback" and bootloader is grub
        use index instead of kernel title ("fallback") as fallback is
        a special option in grub

        @param search_info: can be 'default', position number or title
        @return a dictionary of key->value where key is the type of entry
                information (ex. 'title', 'args', 'kernel', etc) and value
                is the value for that piece of information.
        """
        return self._parse_entry(self._run_boottool('--info=%s' % search_info))


    def get_entries(self):
        """
        Get all entries information.

        @return: a dictionary of index -> entry where entry is a dictionary
                of entry information as described for get_entry().
        """
        raw = "\n" + self._run_boottool('--info=all')
        entries = {}
        for entry_str in raw.split("\nindex"):
            if len(entry_str.strip()) == 0:
                continue
            entry = self._parse_entry("index" + entry_str)
            entries[entry["index"]] = entry

        return entries


    def get_title_for_kernel(self, path):
        """
        Returns a title for a particular kernel.

        @param path: path of the kernel image configured in the boot config
        @return: if the given kernel path is found it will return a string
                with the title for the found entry, otherwise returns None
        """
        entries = self.get_entries()
        for entry in entries.itervalues():
            if entry.get('kernel') == path:
                return entry['title']
        return None


    def add_args(self, kernel, args):
        """
        Add cmdline arguments for the specified kernel.

        @param kernel: can be a position number (index) or title
        @param args: argument to be added to the current list of args
        """

        parameters = ['--update-kernel=%s' % kernel, '--args=%s' % args]

        #add parameter if this is a Xen entry
        if self._xen_mode:
            parameters.append('--xen')

        self._run_boottool(*parameters)


    def remove_args(self, kernel, args):
        """
        Removes specified cmdline arguments.

        @param kernel: can be a position number (index) or title
        @param args: argument to be removed of the current list of args
        """

        parameters = ['--update-kernel=%s' % kernel, '--remove-args=%s' % args]

        #add parameter if this is a Xen entry
        if self._xen_mode:
            parameters.append('--xen')

        self._run_boottool(*parameters)


    def __remove_duplicate_cmdline_args(self, cmdline):
        """
        Remove the duplicate entries in cmdline making sure that the first
        duplicate occurances are the ones removed and the last one remains
        (this is in order to not change the semantics of the "console"
        parameter where the last occurance has special meaning)

        @param cmdline: a space separate list of kernel boot parameters
            (ex. 'console=ttyS0,57600n8 nmi_watchdog=1')
        @return: a space separated list of kernel boot parameters without
            duplicates
        """
        copied = set()
        new_args = []

        for arg in reversed(cmdline.split()):
            if arg not in copied:
                new_args.insert(0, arg)
                copied.add(arg)
        return ' '.join(new_args)


    def add_kernel(self, path, title='autoserv', root=None, args=None,
                   initrd=None, default=False, position='end',
                   xen_hypervisor=None):
        """
        Add a kernel entry to the bootloader (or replace if one exists
        already with the same title).

        @param path: string path to the kernel image file
        @param title: title of this entry in the bootloader config
        @param root: string of the root device
        @param args: string with cmdline args
        @param initrd: string path to the initrd file
        @param default: set to True to make this entry the default one
                (default False)
        @param position: where to insert the new entry in the bootloader
                config file (default 'end', other valid input 'start', or
                # of the title)
        @param xen_hypervisor: xen hypervisor image file (valid only when
                xen mode is enabled)
        """
        if title in self.get_titles():
            self.remove_kernel(title)

        parameters = ['--add-kernel=%s' % path, '--title=%s' % title]

        if root:
            parameters.append('--root=%s' % root)

        if args:
            parameters.append('--args=%s' %
                              self.__remove_duplicate_cmdline_args(args))

        if initrd:
            parameters.append('--initrd=%s' % initrd)

        if default:
            parameters.append('--make-default')

        if position:
            parameters.append('--position=%s' % position)

        # add parameter if this is a Xen entry
        if self._xen_mode:
            parameters.append('--xen')
            if xen_hypervisor:
                parameters.append('--xenhyper=%s' % xen_hypervisor)

        self._run_boottool(*parameters)


    def remove_kernel(self, kernel):
        """
        Removes a specific entry from the bootloader configuration.

        @param kernel: can be 'start', 'end', entry position or entry title.
        """
        self._run_boottool('--remove-kernel=%s' % kernel)


    def boot_once(self, title=None):
        """
        Sets a specific entry for the next boot, then falls back to the
        default kernel.

        @param kernel: title that identifies the entry to set for booting. If
                evaluates to false, this becomes a no-op.
        """
        if title:
            self._run_boottool('--boot-once', '--title=%s' % title)


    def enable_xen_mode(self):
        """
        Enables xen mode. Future operations will assume xen is being used.
        """
        self._xen_mode = True


    def disable_xen_mode(self):
        """
        Disables xen mode.
        """
        self._xen_mode = False


    def get_xen_mode(self):
        """
        Returns a boolean with the current status of xen mode.
        """
        return self._xen_mode
