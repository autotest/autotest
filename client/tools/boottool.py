#!/usr/bin/env python

'''
A boottool clone, but written in python and relying mostly on grubby[1].

[1] - http://git.fedorahosted.org/git/?p=grubby.git
'''

import os, re, sys, optparse, logging, subprocess
import urllib, tarfile, tempfile, shutil, struct


__all__ = ['Grubby', 'OptionParser', 'App']


#
# All options that are first class actions
# One of them should be given on the command line
#
ACTIONS = ['bootloader-probe',
           'arch-probe',
           'add-kernel',
           'boot-once',
           'install',
           'remove-kernel',
           'info',
           'set-default',
           'default',
           'update-kernel',
           # Commands not available in the old boottool
           'grubby-version',
           'grubby-version-check',
           'grubby-install']

#
# When the command line is parsed, 'opts' gets attributes that are named
# after the command line options, but with slight changes
#
ACTIONS_OPT_METHOD_NAME = [act.replace('-', '_') for act in ACTIONS]


#
# Actions (as a opt/method name) that require a --title parameter
#
ACTIONS_REQUIRE_TITLE = ['boot_once', ]


class EfiVar:
    '''
    Helper class to manipulate EFI firmware variables

    This class has no notion of the EFI firmware variables interface, that is,
    where it should read from or write to in order to create or delete EFI
    variables.

    On systems with kernel >= 2.6, that interface is a directory structure
    under /sys/firmware/efi/vars.

    On systems with kernel <= 2.4, that interface is going to be a directory
    structure under /proc/efi/vars. But be advised: this has not been tested
    yet on kernels <= 2.4.
    '''

    GUID_FMT = '16B'
    GUID_CONTENT = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    ATTR_NON_VOLATILE =  0x0000000000000001
    ATTR_BOOTSERVICE_ACCESS = 0x0000000000000002
    ATTR_RUNTIME_ACCESS = 0x0000000000000004

    DEFAULT_ATTRIBUTES = (ATTR_NON_VOLATILE |
                          ATTR_BOOTSERVICE_ACCESS |
                          ATTR_RUNTIME_ACCESS)

    FMT = ('512H' +
           GUID_FMT +
           '1L' +
           '512H' +
           '1L' +
           '1I')


    def __init__(self, name, data, guid=None, attributes=None):
        '''
        Instantiates a new EfiVar

        @type name: string
        @param name: the name of the variable that will be created
        @type data: string
        @param data: user data that will populate the variable
        @type guid: tuple
        @param guid: content for the guid value that composes the full variable
                     name
        @param attributes: integer
        @param attributes: bitwise AND of the EFI attributes this variable will
                           have set
        '''
        self.data = data
        self.name = name

        if guid is None:
            guid = self.GUID_CONTENT
        self.guid = guid

        if attributes is None:
            attributes = self.DEFAULT_ATTRIBUTES
        self.attributes = attributes


    def get_name(self):
        '''
        Returns the variable name in a list ready for struct.pack()
        '''
        l = []
        for i in range(512):
            l.append(0)

        for i in range(len(self.name)):
            l[i] = ord(self.name[i])
        return l


    def get_data(self):
        '''
        Returns the variable data in a list ready for struct.pack()
        '''
        l = []
        for i in range(512):
            l.append(0)

        for i in range(len(self.data)):
            l[i] = ord(self.data[i])
        return l


    def get_packed(self):
        '''
        Returns the EFI variable raw data packed by struct.pack()

        This data should be written to the appropriate interface to create
        an EFI variable
        '''
        params = self.get_name()
        params += self.guid
        params.append((len(self.data) * 2) + 2)
        params += self.get_data()
        params.append(0)
        params.append(self.attributes)

        return struct.pack(self.FMT, *params)


class EfiToolSys:
    '''
    Interfaces with /sys/firmware/efi/vars provided by the kernel

    This interface is present on kernels >= 2.6 with CONFIG_EFI and
    CONFIG_EFI_VARS options set.
    '''

    BASE_PATH = '/sys/firmware/efi/vars'
    NEW_VAR = os.path.join(BASE_PATH, 'new_var')
    DEL_VAR = os.path.join(BASE_PATH, 'del_var')

    def __init__(self):
        pass


    def create_variable(self, name, data, guid=None, attributes=None):
        '''
        Creates a new EFI variable

        @type name: string
        @param name: the name of the variable that will be created
        @type data: string
        @param data: user data that will populate the variable
        @type guid: tuple
        @param guid: content for the guid value that composes the full variable
                     name
        @param attributes: integer
        @param attributes: bitwise AND of the EFI attributes this variable will
                           have set
        '''
        if not self.check_basic_structure():
            return False

        var = EfiVar(name, data, guid, attributes)
        f = open(self.NEW_VAR, 'w')
        f.write(var.get_packed())
        return True


    def delete_variable(self, name, data, guid=None, attributes=None):
        '''
        Delets an existing EFI variable

        @type name: string
        @param name: the name of the variable that will be deleted
        @type data: string
        @param data: user data that will populate the variable
        @type guid: tuple
        @param guid: content for the guid value that composes the full variable
                     name
        @param attributes: integer
        @param attributes: bitwise AND of the EFI attributes this variable will
                           have set
        '''
        if not self.check_basic_structure():
            return False

        var = EfiVar(name, data, guid, attributes)
        f = open(self.DEL_VAR, 'w')
        f.write(var.get_packed())
        return True


    def check_basic_structure(self):
        '''
        Checks the basic directory structure for the /sys/.../vars interface
        '''
        if not os.path.isdir(self.BASE_PATH):
            logging.error('Could not find the base directory interface for '
                         'EFI variables: "%s"', self.BASE_PATH)
            return False

        if not os.path.exists(self.NEW_VAR):
            logging.error('Could not find the file interface for creating new'
                         'EFI variables: "%s"', self.NEW_VAR)
            return False

        if not os.path.exists(self.DEL_VAR):
            logging.error('Could not find the file interface for deleting '
                         'EFI variables: "%s"', self.DEL_VAR)
            return False

        return True


class EliloConf:
    '''
    A simple parser for elilo configuration file

    Has simple features to add and remove global options only, as this is all
    we need. grubby takes care of manipulating the boot entries themselves.
    '''
    def __init__(self, path='/etc/elilo.conf'):
        '''
        Instantiates a new EliloConf

        @type path: string
        @param path: path to elilo.conf
        '''
        self.path = path
        self.global_options_to_add = {}
        self.global_options_to_remove = {}

        self._follow_symlink()


    def _follow_symlink(self):
        '''
        Dereference the path if it's a symlink and make it absolute

        elilo.conf usually is a symlink to the EFI boot partition, so we
        better follow it to the proper location.
        '''
        if os.path.islink(self.path):
            self.path_link = self.path
            self.path = os.path.realpath(self.path_link)

        self.path = os.path.abspath(self.path)


    def add_global_option(self, key, val=None):
        '''
        Adds a global option to the updated elilo configuration file

        @type key: string
        @param key: option name
        @type val: string or None
        @param key: option value or None for options with no values
        @returns: None
        '''
        self.global_options_to_add[key] = val


    def remove_global_option(self, key, val=None):
        '''
        Removes a global option to the updated elilo configuration file

        @type key: string
        @param key: option name
        @type val: string or None
        @param key: option value or None for options with no values
        @returns: None
        '''
        self.global_options_to_remove[key] = val


    def line_to_keyval(self, line):
        '''
        Transforms a text line from the configuration file into a tupple

        @type line: string
        @param line: line of text from the configuration file
        @returns: a tupple with key and value
        '''
        parts = line.split('=', 1)
        key = parts[0].rstrip()
        if len(parts) == 1:
            val = None
        elif len(parts) == 2:
            val = parts[1].strip()
        return (key, val)


    def keyval_to_line(self, keyval):
        '''
        Transforms a tupple into a text line suitable for the config file

        @type keyval: tuple
        @param keyval: a tuple containing key and value
        @returns: a text line suitable for the config file
        '''
        key, val = keyval
        if val is None:
            return '%s\n' % key
        else:
            return '%s=%s\n' % (key, val)


    def matches_global_option_to_remove(self, line):
        '''
        Utility method to check if option is to be removed

        @type line: string
        @param line: line of text from the configuration file
        @returns: True or False
        '''
        key, val = self.line_to_keyval(line)
        if key in self.global_options_to_remove:
            return True
        else:
            return False


    def matches_global_option_to_add(self, line):
        '''
        Utility method to check if option is to be added

        @type line: string
        @param line: line of text from the configuration file
        @returns: True or False
        '''
        key, val = self.line_to_keyval(line)
        if key in self.global_options_to_add:
            return True
        else:
            return False


    def get_updated_content(self):
        '''
        Returns the config file content with options to add and remove applied
        '''
        output = ''

        for key, val in self.global_options_to_add.items():
            output += self.keyval_to_line((key, val))

        eliloconf = open(self.path, 'r')
        for line in eliloconf.readlines():
            if self.matches_global_option_to_remove(line):
                continue
            if self.matches_global_option_to_add(line):
                continue
            else:
                output += line

        eliloconf.close()
        return output


    def update(self):
        '''
        Writes the updated content to the configuration file
        '''
        content = self.get_updated_content()
        eliloconf_write = open(self.path, 'w')
        eliloconf_write.write(content)
        eliloconf_write.close()


def find_executable(executable, favorite_path=None):
    '''
    Returns whether the system has a given executable

    @type executable: string
    @param executable: the name of a file that can be read and executed
    '''
    if os.path.isabs(executable):
        paths = [os.path.basename(executable)]
    else:
        paths = os.environ['PATH'].split(':')
        if favorite_path is not None and favorite_path not in paths:
            paths.insert(0, favorite_path)

    for d in paths:
        f = os.path.join(d, executable)
        if os.path.exists(f) and os.access(f, os.R_OK | os.X_OK):
            return f
    return None


class Grubby(object):
    '''
    Grubby wrapper

    This class calls the grubby binary for most commands, but also
    adds some functionality that is not really suited to be included
    in int, such as boot-once.
    '''

    SUPPORTED_BOOTLOADERS = ('lilo', 'grub2', 'grub', 'extlinux', 'yaboot',
                             'elilo')

    def __init__(self, path='/sbin/grubby', opts=None):
        self.path = path
        self.bootloader = None
        self.opts = opts
        self._set_bootloader()


    #
    # The following block contain utility functions that are used to build
    # most of these class methods, such as methods for running commands
    # and preparing grubby command line switches.
    #
    def _run_get_output(self, arguments):
        '''
        Utility function that runs a command and returns command output
        '''
        logging.debug('Grubby::_run_get_output args: %s', arguments)
        result = None
        try:
            result = subprocess.Popen(arguments, shell=False,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      close_fds=True).stdout.read()
        except:
            pass

        if result is not None:
            result = result.strip()
            logging.debug('Grubby::_run_get_output returnig: %s', result)
        else:
            logging.debug('Grubby::_run_get_output error')
        return result


    def _run_get_output_err(self, arguments):
        '''
        Utility function that runs a command and returns command output
        '''
        logging.debug('Grubby::_run_get_output args: %s', arguments)
        result = None
        try:
            result = subprocess.Popen(arguments, shell=False,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      close_fds=True).stdout.read()
        except:
            pass

        if result is not None:
            result = result.strip()
            logging.debug('Grubby::_run_get_output_err returnig: %s', result)
        else:
            logging.debug('Grubby::_run_get_output_err error')
        return result


    def _run_get_return(self, arguments):
        '''
        Utility function that runs a command and returns status code
        '''
        logging.debug('Grubby::_run_get_output args: %s', arguments)
        result = None
        try:
            result = subprocess.call(arguments)
        except OSError:
            result = -1
            logging.debug('Caught OSError, returning %s', result)

        logging.debug('Grubby::_run_get_return returnig: %s', result)
        return result


    def _set_bootloader(self, bootloader=None):
        '''
        Attempts to detect what bootloader is installed on the system

        The result of this method is used in all other calls to grubby,
        so that it acts accordingly to the bootloader detected.
        '''
        if bootloader is None:
            result = self.get_bootloader()
            if result is not None:
                self.bootloader = result
        else:
            if bootloader in self.SUPPORTED_BOOTLOADERS:
                self.bootloader = bootloader
            else:
                raise ValueError('Bootloader "%s" is not supported' %
                                 bootloader)


    def _run_grubby_prepare_args(self, arguments, include_bootloader=True):
        '''
        Prepares the argument list when running a grubby command
        '''
        args = []
        args.append(self.path)

        # If a bootloader has been detected, that is, a mode has been set,
        # it's passed as the first command line argument to grubby
        if include_bootloader and self.bootloader is not None:
            args.append('--%s' % self.bootloader)

        # Override configuration file
        if self.opts is not None and self.opts.config_file:
            args.append('--config-file=%s' % self.opts.config_file)

        args += arguments
        return args


    def _run_grubby_get_output(self, arguments, include_bootloader=True):
        '''
        Utility function that runs grubby with arguments and returns output
        '''
        args = self._run_grubby_prepare_args(arguments, include_bootloader)
        return self._run_get_output(args)


    def _run_grubby_get_return(self, arguments, include_bootloader=True):
        '''
        Utility function that runs grubby with and returns status code
        '''
        args = self._run_grubby_prepare_args(arguments, include_bootloader)
        return self._run_get_return(args)


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
            name, value = line.split('=', 1)
            name = name.strip()
            value = value.strip()

            if name == 'index':
                # index values are integrals
                value = int(value)
            entry[name] = value

        return entry


    def _extract_tarball(self, tarball, directory):
        '''
        Extract tarball into the an directory

        This code assume the first (or only) entry is the main directory

        @type tarball: string
        @param tarball: tarball file path
        @type directory: string
        @param directory: directory path
        @return: path of toplevel directory as extracted from tarball
        '''
        f = tarfile.open(tarball)
        members = f.getmembers()
        topdir = members[0]
        assert topdir.isdir()
        # we can not use extractall() because it is not available on python 2.4
        for m in members:
            f.extract(m, directory)
        return os.path.join(directory, topdir.name)


    def _max_index(self, info):
        '''
        Returns the maximum index number found in a get_info() output

        @type info: list of lines
        @param info: result of utility method get_info()
        @returns: maximum index number
        '''
        indexes = [l[6:] for l in info if l.startswith('index=')]
        indexes = map(int, indexes)
        return max(indexes)


    def _index_for_title(self, title):
        '''
        Returns the index of an entry based on the title of the entry

        @type title: string
        @param title: the title of the entry
        @returns: the index of the given entry or None
        '''
        logging.debug('Grubby::_index_for_title %s', title)

        if self._is_number(title):
            return title

        info = self.get_info_lines()
        max_index = self._max_index(info)

        for i in range(0, max_index + 1):
            info = self.get_info(i)
            if info is None:
                continue
            lines = info.splitlines()
            looking_for = ('title=%s' % title,
                           'label=%s' % title)
            for line in lines:
                if line in looking_for:
                    return i
        return None


    def _info_filter(self, info, key, value=None):
        '''
        Filters info, looking for keys, optionally set with a given value

        @type info: list of lines
        @param info: result of utility method get_info()
        @type key: string
        @param key: filter based on this key
        @type value: string
        @param value: filter based on this value
        @returns: value or None
        '''
        for line in info:
            if value is not None:
                looking_for = '%s=%s' % (key, value)
                if line == looking_for:
                    return line.split("=")[1]
            else:
                if line.startswith("%s=" % key):
                    return line.split("=")[1]
        return None


    def _kernel_for_title(self, title):
        '''
        Returns the kernel path for an entry based on its title

        @type title: string
        @param title: the title of the entry
        @returns: the kernel path of None
        '''
        index = self._index_for_title(title)
        if index is not None:
            info = self.get_info_lines(index)
            kernel = self._info_filter(info, 'kernel')
            return kernel
        else:
            return None


    def _is_number(self, data):
        '''
        Returns true if supplied data is an int or string with digits
        '''
        if isinstance(data, int):
            return True
        elif isinstance(data, str) and data.isdigit():
            return True
        return False


    def _get_entry_selection(self, data):
        '''
        Returns a valid grubby parameter for commands such as --update-kernel
        '''
        if self._is_number(data):
            return data
        elif isinstance(data, str) and data.startswith('/'):
            # assume it's the kernel filename
            return data
        elif isinstance(data, str):
            return self._kernel_for_title(data)
        else:
            raise ValueError("Bad value for 'kernel' parameter. Expecting "
                             "either and int (index) or string (kernel or "
                             "title)")


    def _remove_duplicate_cmdline_args(self, cmdline):
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


    #
    # The following methods implement a form of "API" that action methods
    # can rely on. Another goal is to maintain compatibility with the current
    # client side API in autotest (client/common_lib/boottool.py)
    #
    def get_bootloader(self):
        '''
        Get the bootloader name that is detected on this machine

        This module performs the same action as client side boottool.py
        get_type() method, but with a better name IMHO.

        @returns: name of detected bootloader
        '''
        args = [self.path, '--bootloader-probe']
        output = self._run_get_output_err(args)
        if output is None:
            return None
        if output.startswith('grubby: bad argument'):
            return None
        elif output not in self.SUPPORTED_BOOTLOADERS:
            return None
        return output


    # Alias for client side boottool.py API
    get_type = get_bootloader

    # Alias for boottool app
    bootloader_probe = get_bootloader


    def get_architecture(self):
        '''
        Get the system architecture

        This is much simpler version then the original boottool version, that
        does not attempt to filter the result of the command / system call
        that returns the archicture.

        @returns: string with system archicteture, such as x86_64, ppc64, etc
        '''
        return os.uname()[4]


    # Alias for boottool app
    arch_probe = get_architecture


    def get_titles(self):
        '''
        Get the title of all boot entries.

        @returns: list with titles of boot entries
        '''
        info = self.get_info_lines()
        return [l[6:] for l in info if (l.startswith('title=') or
                                        l.startswith('label='))]


    def get_default_index(self):
        '''
        Get the default entry index.

        This module performs the same action as client side boottool.py
        get_default() method, but with a better name IMHO.

        @returns: an string with the the default entry.
        '''
        return self._run_grubby_get_output(['--default-index'])


    # Alias for client side boottool.py API
    get_default = get_default_index

    # Alias for boottool app
    default = get_default_index


    def set_default_by_index(self, index):
        """
        Set the default boot entry.

        This module performs the same action as client side boottool.py
        set_default() method, but with a better name IMHO.

        @param index: entry index number to set as the default.
        """
        pass


    # Alias for client side boottool.py API
    set_default = set_default_by_index


    def get_default_title(self):
        '''
        Get the default entry title.

        Conforms to the client side boottool.py API, but rely directly on
        grubby functionality.

        @returns: a string of the default entry title.
        '''
        return self._run_grubby_get_output(['--default-title'])


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
        info = self.get_info(search_info)
        return self._parse_entry(info)


    def get_entries(self):
        """
        Get all entries information.

        @return: a dictionary of index -> entry where entry is a dictionary
                of entry information as described for get_entry().
        """
        info = self.get_info_lines()
        max_index = self._max_index(info)

        entries = {}
        for i in range(0, max_index):
            entries[i] = self.get_entry(i)

        return entries


    def get_info(self, entry='ALL'):
        '''
        Returns information on a given entry, or all of them if not specified

        The information is returned as a set of lines, that match the output
        of 'grubby --info=<entry>'

        @type entry: string
        @param entry: entry description, usually an index starting from 0
        @returns: set of lines
        '''
        logging.debug('Grubby::get_info')
        command = '--info=%s' % entry
        info = self._run_grubby_get_output([command])
        if info:
            return info


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
        entry_selection = self._get_entry_selection(kernel)
        command_arguments = ['--update-kernel=%s' % entry_selection,
                             '--args=%s' % args]
        self._run_grubby_get_return(command_arguments)


    def remove_args(self, kernel, args):
        """
        Removes specified cmdline arguments.

        @param kernel: can be a position number (index) or title
        @param args: argument to be removed of the current list of args
        """
        entry_selection = self._get_entry_selection(kernel)
        command_arguments = ['--update-kernel=%s' % entry_selection,
                             '--remove-args=%s' % args]
        self._run_grubby_get_return(command_arguments)


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

        # FIXME: grubby takes no --root parameter
        # if root:
        #     parameters.append('--root=%s' % root)

        if args:
            parameters.append('--args=%s' %
                              self._remove_duplicate_cmdline_args(args))

        if initrd:
            parameters.append('--initrd=%s' % initrd)

        if default:
            parameters.append('--make-default')

        # There's currently an issue with grubby '--add-to-bottom' feature.
        # Because it uses the tail instead of the head of the list to add
        # a new entry, when copying a default entry as a template
        # (--copy-default), it usually copies the "recover" entries that
        # usually go along a regular boot entry, specially on grub2.
        #
        # So, for now, until I fix grubby, we'll *not* respect the position
        # (--position=end) command line option.
        #
        # if opts.position == 'end':
        #     parameters.append('--add-to-bottom')

        parameters.append("--copy-default")
        return self._run_grubby_get_return(parameters)


    def remove_kernel(self, kernel):
        """
        Removes a specific entry from the bootloader configuration.

        @param kernel: entry position or entry title.

        FIXME: param kernel should also take 'start' or 'end'.
        """
        entry_selection = self._get_entry_selection(kernel)
        if entry_selection is None:
            logging.debug('No kernel found for title "%s". Assuming no entry'
                          'exists, and emulating boottool(.pl) behavior being '
                          'silent about it.', kernel)
            return 0

        command_arguments = ['--remove-kernel=%s' % entry_selection]
        return self._run_grubby_get_return(command_arguments)


    #
    # The following methods are not present in the original client side
    # boottool.py
    #
    def get_info_lines(self, entry='ALL'):
        '''
        Returns information on a given entry, or all of them if not specified

        The information is returned as a set of lines, that match the output
        of 'grubby --info=<entry>'

        @type entry: string
        @param entry: entry description, usually an index starting from 0
        @returns: set of lines
        '''
        info = self.get_info(entry)
        if info:
            return info.splitlines()


    def get_grubby_version_raw(self):
        '''
        Get the version of grubby that is installed on this machine as is

        @returns: string with raw output from grubby --version
        '''
        return self._run_grubby_get_output(['--version'], False)


    def get_grubby_version(self):
        '''
        Get the version of grubby that is installed on this machine

        @returns: tupple with (major, minor) grubby version
        '''
        output = self.get_grubby_version_raw()
        if output is None:
            logging.warn('Could not run grubby to fetch its version')
            return None

        match = re.match('(grubby version)?(\s)?(\d)\.(\d)(.*)', output)
        if match:
            groups = match.groups()
            return (int(groups[2]), int(groups[3]))
        else:
            return None


    def grubby_install(self):
        '''
        Attempts to install a recent enough version of grubby

        So far tested on:
           * Fedora 16 x86_64
           * Debian 6 x86_64
           * SuSE 12.1 x86_64
           * RHEL 4 on ia64 (with updated python 2.4)
           * RHEL 5 on ia64
           * RHEL 6 on ppc64
        '''
        def patch_makefile():
            '''
            Patch makefile, making CFLAGS more forgivable to older toolchains
            '''
            cflags_line = 'CFLAGS += $(RPM_OPT_FLAGS) -std=gnu99 -ggdb\n'
            libs_line = 'grubby_LIBS = -lblkid -lpopt -luuid\n'
            shutil.move('Makefile', 'Makefile.boottool.bak')
            o = open('Makefile', 'w')
            for l in open('Makefile.boottool.bak').readlines():
                if l.startswith('CFLAGS += '):
                    o.write(cflags_line)
                elif l.startswith('grubby_LIBS = -lblkid -lpopt'):
                    o.write(libs_line)
                else:
                    o.write(l)
            o.close()

        topdir = tempfile.mkdtemp()
        tarball_uri = ('http://pkgs.fedoraproject.org/repo/pkgs/grubby/'
                       'grubby-8.9.tar.bz2/f0f27d7e78ad1452e7d0bf0bf4ca'
                       '0fc6/grubby-8.9.tar.bz2')
        tarball_name = os.path.basename(tarball_uri)
        tarball = os.path.join(topdir, tarball_name)

        urllib.urlretrieve(tarball_uri, tarball)

        srcdir = os.path.join(topdir, 'src')
        install_root = os.path.join(topdir, 'install_root')
        os.mkdir(install_root)

        srcdir = self._extract_tarball(tarball, srcdir)
        os.chdir(srcdir)
        patch_makefile()
        os.system('make 2>&1 >/dev/null')
        os.environ['DESTDIR'] = install_root
        os.system('make install 2>&1 >/dev/null')

        grubby_system_path = '/sbin/grubby'
        grubby_backup_path = '/sbin/grubby.boottool.bkp'
        if (os.path.exists(grubby_system_path)
            and not os.path.exists(grubby_backup_path)):
            shutil.move(grubby_system_path, grubby_backup_path)

        grubby_bin = os.path.join(install_root, 'sbin', 'grubby')
        shutil.copy(grubby_bin, grubby_system_path)


    def boot_once(self, title=None):
        '''
        Configures the bootloader to boot an entry only once

        This is not implemented by grubby, but directly implemented here, via
        the 'boot_once_<bootloader>' method.
        '''
        logging.debug('Title chosen to boot once: %s', title)

        available_titles = self.get_titles()
        if title not in available_titles:
            logging.error('Entry with title "%s" was not found', title)
            return -1

        default_title = self.get_default_title()
        logging.debug('Title actually set as default: %s', default_title)

        if default_title == title:
            logging.info('Doing nothing: entry to boot once is the same as '
                         'default entry')
            return
        else:
            logging.debug('Setting boot once for entry: %s', title)


        bootloader = self.get_bootloader()
        if bootloader in ('grub', 'grub2', 'elilo'):
            entry_index = self._index_for_title(title)
            if entry_index is None:
                logging.error('Could not find index for entry with title "%s"',
                              title)
                return -1

        if bootloader == 'grub':
            return self.boot_once_grub(entry_index)
        elif bootloader == 'grub2':
            return self.boot_once_grub2(entry_index)
        elif bootloader == 'yaboot':
            return self.boot_once_yaboot(title)
        elif bootloader == 'elilo':
            if os.path.isdir('/sys/firmware/efi/vars'):
                return self.boot_once_elilo(entry_index)
            elif os.path.isdir('/proc/efi/vars'):
                logging.error('boottool currently does not support setting '
                              'boot once on a kernel 2.4 linux system')
                return -1
            else:
                logging.error('Detected bootloader as elilo, but could not '
                              'find interface for managing EFI variables')
                return -1
        else:
            logging.error("Detected bootloader does not implement boot once")
            return -1


    def boot_once_grub(self, entry_index):
        '''
        Implements the boot once feature for the grub bootloader
        '''
        # XXX: check the type of default set (numeric or "saved")
        grub_instructions = ['savedefault --default=%s --once' % entry_index,
                             'quit']
        grub_instructions_text = '\n'.join(grub_instructions)
        grub_binary = '/sbin/grub'

        p = subprocess.Popen([grub_binary, '--batch'],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate(grub_instructions_text)

        if err is not None:
            harmless = ['Probing devices to guess BIOS drives. '
                        'This may take a long time.']
            err_lines = err.splitlines()
            err_harmful = [l for l in err_lines if l and l not in harmless]

            if err_harmful:
                logging.error("Error while running grub to set boot once: %s",
                              "\n".join(err_harmful))
                return False

        logging.debug('No error detected while running grub to set boot once')
        return 0


    def boot_once_grub2(self, entry_index):
        '''
        Implements the boot once feature for the grub2 bootloader

        Caveat: this assumes the default set is of type "saved", and not a
        numeric value.
        '''
        grub_reboot_names = ['grub-reboot',
                             'grub2-reboot']
        executable = None
        for grub_reboot in grub_reboot_names:
            executable = find_executable(grub_reboot)
            if executable is not None:
                break

        if executable is None:
            logging.error('Could not find executable among searched names: %s',
                          ' ,'.join(grub_reboot_names))
            return -1

        return self._run_get_return([executable,
                                     '%s' % entry_index])


    def boot_once_yaboot(self, entry_title):
        '''
        Implements the boot once feature for the yaboot bootloader
        '''
        return self._run_get_return(['/usr/sbin/nvsetenv',
                                     'boot-once',
                                     entry_title])


    def boot_once_elilo(self, entry_index):
        '''
        Implements boot once for machines with kernel >= 2.6

        This manipulates EFI variables via the interface available at
        /sys/firmware/efi/vars
        '''
        info = self.get_entry(entry_index)
        kernel = os.path.basename(info['kernel'])

        # remove quotes
        args = info['args']
        if args[0] == '"':
            args = args[1:]
        if args[-1] == '"':
            args = args[:-1]

        params = "root=%s %s" % (info['root'], args)
        data = "%s %s" % (kernel, params)

        efi = EfiToolSys()
        if not (efi.create_variable('EliloAlt', data)):
            return -1

        eliloconf = EliloConf()
        eliloconf.add_global_option('checkalt')
        eliloconf.add_global_option('initrd', os.path.basename(info['initrd']))
        eliloconf.remove_global_option('prompt')
        eliloconf.update()
        return 0


class OptionParser(optparse.OptionParser):
    '''
    Command line option parser

    Aims to maintain compatibility at the command line level with boottool
    '''

    option_parser_usage = '''%prog [options]'''

    def __init__(self, **kwargs):
        optparse.OptionParser.__init__(self,
                                       usage=self.option_parser_usage,
                                       **kwargs)

        misc = self.add_option_group('MISCELLANEOUS OPTIONS')
        misc.add_option('--config-file',
                        help='Specifies the path and name of the bootloader '
                        'config file, overriding autodetection of this file')

        misc.add_option('--force', action='store_true',
                        help='If specified, any conflicting kernels will be '
                        'removed')

        misc.add_option('--bootloader',
                        help='Manually specify the bootloader to use.  By '
                        'default, boottool will automatically try to detect '
                        'the bootloader being used')

        misc.add_option('--root',
                        help='The device where the root partition is located')

        misc.add_option('--debug', default=0,
                        help='Prints debug messages. This expects a numerical '
                        'argument corresponding to the debug message '
                        'verbosity')

        probe = self.add_option_group('SYSTEM PROBING')
        probe.add_option('--bootloader-probe', action='store_true',
                         help='Prints the bootloader in use on the system '
                         'and exits')

        probe.add_option('--arch-probe', action='store_true',
                         help='Prints the arch of the system and exits')

        actions = self.add_option_group('ACTIONS ON BOOT ENTRIES')
        actions.add_option('--add-kernel',
                           help='Adds a new kernel with the given path')

        actions.add_option('--remove-kernel',
                           help='Removes the bootloader entry with the given '
                           'position or title. Also accepts \'start\' or '
                           '\'end\'')

        actions.add_option('--update-kernel',
                           help='Updates an existing kernel with the given '
                           'position number or title. Useful options when '
                           'modifying a kernel include --args and '
                           '--remove-args')

        actions.add_option('--info',
                        help='Display information about the bootloader entry '
                        'at the given position number. Also accepts \'all\' '
                        'or \'default\'')

        actions.add_option('--default', action='store_true',
                           help='Prints the current default kernel for the '
                           'bootloader')

        actions.add_option('--set-default',
                           help='Updates the bootloader to set the default '
                           'boot entry to given given position or title')

        actions.add_option('--install', action='store_true',
                           help='Causes bootloader to update and re-install '
                           'the bootloader file')

        actions.add_option('--boot-once', action='store_true',
                           help='Causes the bootloader to boot the kernel '
                           'specified by --title just one time, then fall back'
                           ' to the default entry. This option does not work '
                           'identically on all architectures')

        act_args = self.add_option_group('ACTION PARAMETERS')
        act_args.add_option('--title',
                            help='The title or label to use for the '
                            'bootloader entry. Required when adding a new '
                            'entry.')

        act_args.add_option('--position',
                            help='Insert bootloader entry at the given '
                            'position number, counting from 0. Also accepts '
                            '\'start\' or \'end\'. Optional when adding a new '
                            'entry.')

        act_args.add_option('--make-default', action='store_true',
                            help='Specifies that the bootloader entry being '
                            'added should be the new default')

        kernel = self.add_option_group('LINUX KERNEL PARAMETERS',
                                       'Options specific to manage boot '
                                       'entries with Linux')
        kernel.add_option('--args',
                          help='Add arguments to be passed to the kernel at '
                          'boot. Use when adding a new entry or when '
                          'modifying an existing entry.')

        kernel.add_option('--remove-args',
                          help='Arguments to be removed from an existing entry'
                          '. Use when modifying an existing entry with '
                          '--update-kernel action.')

        kernel.add_option('--initrd',
                          help='The initrd image path to use in the bootloader '
                          'entry')

        kernel.add_option('--module',
                          help='This option adds modules to the new kernel. It'
                          ' only works with Grub Bootloader. For more module '
                          'options just add another --module parameter')

        grubby = self.add_option_group('GRUBBY',
                                       'Manage grubby, the tool that drives '
                                       'most of boottool functionality')
        grubby.add_option('--grubby-version', action='store_true',
                          help='Prints the version of grubby installed on '
                          'this machine')

        grubby.add_option('--grubby-version-check',
                          help='Checks if the installed version of grubby is '
                          'recent enough')

        grubby.add_option('--grubby-install', action='store_true',
                          help='Attempts to install a recent enought version '
                          'of grubby')

        grubby.add_option('--grubby-path',
                          help='Use a different grubby binary, located at the '
                          'given path')


    def opts_has_action(self, opts):
        '''
        Checks if (parsed) opts has a first class action
        '''
        global ACTIONS_OPT_METHOD_NAME
        has_action = False
        for action in ACTIONS_OPT_METHOD_NAME:
            value = getattr(opts, action)
            if value is not None:
                has_action = True
        return has_action


    def opts_get_action(self, opts):
        '''
        Gets the selected action from the parsed opts
        '''
        global ACTIONS_OPT_METHOD_NAME
        for action in ACTIONS_OPT_METHOD_NAME:
            value = getattr(opts, action)
            if value is not None:
                return action
        return None


    def check_values(self, opts, args):
        '''
        Validate the option the user has supplied
        '''
        # check if an action has been selected
        if not self.opts_has_action(opts):
            self.print_help()
            raise SystemExit

        # check if action needs a --title option
        action = self.opts_get_action(opts)
        if action in ACTIONS_REQUIRE_TITLE:
            if opts.title is None:
                print 'Action %s requires a --title parameter' % action
                raise SystemExit

        return (opts, args)


class BoottoolApp(object):
    '''
    The boottool application itself
    '''
    def __init__(self):
        self.opts = None
        self.args = None
        self.option_parser = OptionParser()
        self.grubby = None


    def _parse_command_line(self):
        '''
        Parsers the command line arguments
        '''
        (self.opts,
         self.args) = self.option_parser.parse_args()


    def _configure_logging(self):
        '''
        Configures logging based on --debug= command line switch

        We do not have as many levels as the original boottool(.pl) had, but
        we accept the same range of parameters and adjust it to our levels.
        '''
        log_map = {0 : logging.ERROR,
                   1 : logging.WARNING,
                   2 : logging.INFO,
                   3 : logging.DEBUG}
        try:
            level = int(self.opts.debug)
        except ValueError:
            level = 0

        max_level = max(log_map.keys())
        if level > max_level:
            level = max_level

        logging_level = log_map.get(level)
        logging.basicConfig(level=logging_level,
                            format="%(levelname)s: %(message)s")


    def _install_grubby_if_missing(self):
        '''
        Installs grubby if it's missing on this system

        Or if the required version is not sufficient for the needs of boottool
        '''
        executable = find_executable('grubby', '/sbin')
        if executable is not None:
            required_version = (8, 9)
            grubby = Grubby(executable)
            current_version = grubby.get_grubby_version()
            if current_version is None:
                logging.error('Could not version for grubby executable "%s"',
                              executable)
                sys.exit(-1)

            if current_version < required_version:
                logging.info('Installing grubby because currently installed '
                             'version (%s.%s) is not recent enough',
                             current_version[0], current_version[1])
                grubby.grubby_install()
        else:
            logging.info('Installing grubby because it was not found on this '
                         'system')
            grubby = Grubby()
            grubby.grubby_install()

        grubby = Grubby()
        installed_version = grubby.get_grubby_version_raw()
        logging.info('Installed grubby version: %s', installed_version)


    def run(self):
        self._parse_command_line()
        self._configure_logging()
        self._install_grubby_if_missing()

        # if we made this far, the command line checking succeeded
        if self.opts.grubby_path:
            self.grubby = Grubby(self.opts.grubby_path, self.opts)
        else:
            self.grubby = Grubby(opts=self.opts)

        if self.opts.bootloader:
            logging.debug('Forcing bootloader "%s"', self.opts.bootloader)
            try:
                self.grubby._set_bootloader(self.opts.bootloader)
            except ValueError, msg:
                logging.error(msg)
                sys.exit(-1)

        #
        # The following implements a simple action -> method dispatcher
        # First, we look for a method named action_ + action_name on the
        # app instance itself. If not found, we try to find a method with
        # the same name as the action in the grubby instance.
        #
        action_name = self.option_parser.opts_get_action(self.opts)
        try:
            action_method = getattr(self, "action_%s" % action_name)
        except AttributeError:
            action_method = getattr(self.grubby, action_name)

        if action_method:
            result = action_method()
            if result is None:
                result = 0
            elif isinstance(result, str):
                print result
                result = 0
            sys.exit(result)


    #
    # The following block implements actions. Actions are methods that will be
    # called because of user supplied parameters on the command line. Most
    # actions, such as the ones that query information, are built around the
    # "API" methods defined in the previous block
    #
    def action_grubby_version(self):
        '''
        Prints the of grubby that is installed on this machine
        '''
        logging.debug('BoottoolApp::action_grubby_version')
        version = self.grubby.get_grubby_version()
        if version is not None:
            print "%s.%s" % version
            return

        version = self.grubby.get_grubby_version_raw()
        if version is not None:
            print version


    def action_grubby_version_check(self):
        '''
        Prints the of grubby that is installed on this machine
        '''
        logging.debug('BoottoolApp::action_grubby_version_check')

        current_version = self.grubby.get_grubby_version()
        if current_version is None:
            logging.warn('Could not get version numbers from grubby')
            return -1

        required_version = self.opts.grubby_version_check.split('.', 1)
        required_version_major = required_version[0]
        if len(required_version) == 1:
            req_version = (int(required_version_major), 0)
        else:
            req_version = (int(required_version_major),
                           int(required_version[1]))

        if current_version >= req_version:
            return 0
        else:
            return -1


    def action_grubby_install(self):
        '''
        Attempts to install a recent enough version of grubby
        '''
        logging.debug('BoottoolApp::action_grubby_install')
        return self.grubby.grubby_install()


    def action_info(self):
        '''
        Prints boot entry information

        boottool is frequently called with 'all' lowercase, but
        grubby expects it to be uppercase
        '''
        logging.debug('BoottoolApp::action_info')

        if not self.opts.info:
            logging.error('Kernel title to update is required')
            return -1

        info_index = self.opts.info
        if not ((info_index.lower() == 'all') or
                (self.opts.info.isdigit())):
            logging.error('Parameter to info should be either "all", "ALL" '
                          'or an integer index')
            return -1

        if info_index == 'all':
            info_index = 'ALL'

        info = self.grubby.get_info_lines(info_index)
        if info:
            for line in info:
                if line.startswith('index='):
                    print
                # for now, omit boot. boottool prints a grub device (hd0,0)
                elif line.startswith('boot='):
                    continue

                key, val = line.split('=', 1)

                # remove quotes
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]

                print '%-8s: %s' % (key, val)


    def action_add_kernel(self):
        '''
        Adds a new boot entry based on the values of other command line options

        @type opts: object
        @param opts: parsed command line options
        @returns:
        '''
        logging.debug('BoottoolApp::action_add_kernel')

        if not self.opts.add_kernel:
            logging.error("Kernel to add is required")
            return -1

        if not self.opts.title:
            logging.error("Kernel title is required")
            return -1

        if not self.opts.initrd:
            logging.error("initrd is required")
            return -1

        return self.grubby.add_kernel(self.opts.add_kernel,
                                      self.opts.title,
                                      args=self.opts.args,
                                      initrd=self.opts.initrd)


    def action_update_kernel(self):
        '''
        Updates a kernel entry
        '''
        logging.debug('Grubby::action_update_kernel')

        if not self.opts.update_kernel:
            logging.error("Kernel title to update is required")
            return -1

        args = []

        kernel = self.grubby._get_entry_selection(self.opts.update_kernel)
        if kernel is not None:
            args.append("--update-kernel=%s" % kernel)

        if self.opts.args:
            args.append("--args=%s" % self.opts.args)

        if self.opts.remove_args:
            args.append("--remove-args=%s" % self.opts.remove_args)

        return self.grubby._run_grubby_get_return(args)


    def action_remove_kernel(self):
        '''
        Removes a boot entry by the specified title

        boottool expects: title
        grubby expects: kernel path or special syntax (eg, TITLE=)
        '''
        logging.debug('BoottoolApp::action_remove_kernel')

        if not self.opts.remove_kernel:
            logging.error("Kernel title to remove is required")
            return -1

        return self.grubby.remove_kernel(self.opts.remove_kernel)


    def action_boot_once(self):
        """
        Sets a specific entry for the next boot only

        The subsequent boots will use the default kernel
        """
        logging.debug('BoottoolApp::action_boot_once')

        if not self.opts.boot_once:
            logging.error("Kernel to boot once is required")

        return self.grubby.boot_once(self.opts.title)


if __name__ == '__main__':
    app = BoottoolApp()
    app.run()
