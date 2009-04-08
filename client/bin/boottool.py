import shutil, re, os, string
from autotest_lib.client.common_lib import utils, error

class boottool(object):
    def __init__(self, boottool_exec=None):
        #variable to indicate if in mode to write entries for Xen
        self.xen_mode = False

        if boottool_exec:
            self.boottool_exec = boottool_exec
        else:
            autodir = os.environ['AUTODIR']
            self.boottool_exec = autodir + '/tools/boottool'

        if not self.boottool_exec:
            raise error.AutotestError('Failed to set boottool_exec')


    def _remove_duplicate_args(self, args):
        """
        Remove the duplicate entries in args making sure that the first
        duplicate occurances are the ones removed and the last one remains
        (this is in order to not change the semantics of the "console"
        parameter where the last occurance has special meaning)

        @param args: a space separate list of kernel boot parameters
            (ex. 'console=ttyS0,57600n8 nmi_watchdog=1')
        @return: a space separated list of kernel boot parameters without
            duplicates
        """
        copied = set()
        new_args = []

        for arg in reversed(args.split()):
            if arg not in copied:
                new_args.insert(0, arg)
                copied.add(arg)
        return ' '.join(new_args)


    def run_boottool(self, params):
        return utils.system_output('%s %s' % (self.boottool_exec, params))


    def bootloader(self):
        return self.run_boottool('--bootloader-probe')


    def architecture(self):
        return self.run_boottool('--arch-probe')


    def __get_key_values_from_entries(self, key):
        """
        Helper method to get key values from boot entries

            @param key: one of the keys in boot entry.
                         e.g. index, title, args, kernel, root
        """

        regex = re.compile('^%s\s*:\s*(.*)' % key)
        lines = self.run_boottool('--info all').splitlines()
        key_values = []
        for line in lines:
            match = regex.match(line)
            if match:
                key_values.append(match.group(1))

        return key_values


    def get_titles(self):
        """ Returns a list of boot entries titles """
        return self.__get_key_values_from_entries("title")


    def get_indexes(self):
        """ Returns a list of boot entries indexes """
        return self.__get_key_values_from_entries("index")


    def get_default_title(self):
        default = int(self.get_default())
        return self.get_titles()[default]


    def get_title_for_kernel(self, path):
        """
        Returns a title for a particular kernel.

            @param path: full path to vmlinuz
            @rtype: str
        """
        entries = self.get_entries()
        for entry in entries.values():
            try:
                if entry['kernel'] == path:
                    return entry['title']
            except KeyError:
                pass
        return None


    def print_entry(self, index):
        """
        Prints entry to stdout as returned by perl boottool

            @deprecated: use get_entry instead
        """
        print self.run_boottool('--info=%s' % index)


    def get_entries(self):
        """
        Get all entries

            @rtype: dict
        """
        raw = "\n" + self.run_boottool('--info all')
        entries = {}
        for entry_str in raw.split("\nindex"):
            if len(entry_str.strip()) == 0:
                continue
            entry = self.parse_entry("index" + entry_str)
            entries[entry["index"]] = entry

        return entries


    def get_entry(self, kernel):
        """
        Get entry

        NOTE: if entry is "fallback" and bootloader is grub
        use index instead of kernel title ("fallback") as fallback is
        a special option in grub

            @param kernel: can be a position number (index) or title
            @rtype: dict
        """
        return self.parse_entry(self.run_boottool('--info="%s"' % kernel))


    def parse_entry(self, entry_str):
        """
        Parse entry as returned by perl boottool

            @param entry_str: one entry from perl boottool
            @rtype: dict
        """
        entry = {}
        for line in entry_str.splitlines():
            if len(line) == 0:
                continue
            name = line[:line.find(":")]
            value = line[line.find(":") + 1:]
            entry[name.strip()] = value.strip()

        return entry


    def get_default(self):
        return self.run_boottool('--default').strip()


    def set_default(self, index):
        print self.run_boottool('--set-default=%s' % index)


    def enable_xen_mode(self):
        self.xen_mode = True


    def disable_xen_mode(self):
        self.xen_mode = False


    def get_xen_mode(self):
        return self.xen_mode


    def add_args(self, kernel, args):
        """
        Add specified argument

            @param kernel: can be a position number (index) or title
            @param args: argument to be added to the current list of args
        """

        parameters = '--update-kernel="%s" --args="%s"' % (kernel, args)

        #add parameter if this is a Xen entry
        if self.xen_mode:
            parameters += ' --xen'

        print self.run_boottool(parameters)


    def add_xen_hypervisor_args(self, kernel, args):
        self.run_boottool('--xen --update-xenhyper=%s --xha="%s"') %(kernel, args)


    def remove_args(self, kernel, args):
        """
        Removes specified argument

            @param kernel: can be a position number (index) or title
            @param args: argument to be removed of the current list of args
        """

        parameters = '--update-kernel="%s" --remove-args="%s"' % (kernel, args)

        #add parameter if this is a Xen entry
        if self.xen_mode:
            parameters += ' --xen'

        print self.run_boottool(parameters)


    def remove_xen_hypervisor_args(self, kernel, args):
        self.run_boottool('--xen --update-xenhyper=%s --remove-args="%s"') \
                % (kernel, args)


    def add_kernel(self, path, title='autotest', initrd='', xen_hypervisor='',
                   args=None, root=None, position='end', force=False):

        parameters = ""
        if force:
            parameters += " --force "

        parameters += '--add-kernel=%s --title=%s' % (path, title)

        # add an initrd now or forever hold your peace
        if initrd:
            parameters += ' --initrd=%s' % initrd

        # add parameter if this is a Xen entry
        if self.xen_mode:
            parameters += ' --xen'
            if xen_hypervisor:
                parameters += ' --xenhyper=%s' % xen_hypervisor

        if args:
            parameters += ' --args="%s"' % self._remove_duplicate_args(args)
        if root:
            parameters += ' --root="%s"' % root
        if position:
            parameters += ' --position="%s"' % position

        print self.run_boottool(parameters)


    def remove_kernel(self, kernel):
        print self.run_boottool('--remove-kernel=%s' % kernel)


    def boot_once(self, title=None):
        if not title:
            title = self.get_default_title()
        print self.run_boottool('--boot-once --title=%s' % title)


    def info(self, index):
        return self.run_boottool('--info=%s' % index)


    def install(self):
        return self.run_boottool('--install')


# TODO:  backup()
# TODO:  set_timeout()
