import email.Message, os, re, smtplib

from autotest_lib.server import frontend

class trigger(object):
    """
    Base trigger class. You are allowed to derive from it and
    override functions to suit your needs in the configuration file.
    """
    def __init__(self):
        self.__actions = []


    def run(self, files):
        # Call each of the actions and pass in the kernel list
        for action in self.__actions:
            action(files)


    def add_action(self, func):
        self.__actions.append(func)


class base_action(object):
    """
    Base class for functor actions. Since actions can also be simple functions
    all action classes need to override __call__ to be callable.
    """
    def __call__(self, kernel_list):
        """
        Perform the action for that given kernel filenames list.

        @param kernel_list: a sequence of kernel filenames (strings)
        """
        raise NotImplemented('__call__ not implemented')


class map_action(base_action):
    """
    Action that uses a map between machines and their associated control
    files and kernel configuration files and it schedules them using
    the AFE.
    """

    _PREAMBLE = """# autotest/mirror/mirror generated preamble
kernel = %s
config = %s

"""

    _AUTOTEST_WRAPPER = """def step_init():
    job.next_step([step_test])
    testkernel = job.kernel(kernel)

    if config:
        testkernel.config(config)
    else:
        testkernel.config('', None, True)
    testkernel.build()
    testkernel.boot()

def step_test():
"""

    _encode_sep = re.compile('(\D+)')

    class machine_info(object):
        """
        Class to organize the machine associated information for this action.
        """
        def __init__(self, control_files, kernel_configs):
            """
            Instantiate a machine_info object.

            @param control_files: a sequence of control file names to run for
                    this host ("~" inside the filename will be expanded)
            @param kernel_configs: a dictionary of
                    kernel_version -> config_filename associating kernel
                    versions with corresponding kernel configuration files
                    ("~" inside the filename will be expanded)
            """
            self.control_files = control_files
            self.kernel_configs = kernel_configs


    def __init__(self, control_map, jobname_pattern):
        """
        Instantiate a map_action.

        @param control_map: a dictionary of hostname -> machine_info
        """
        self._control_map = control_map
        self._jobname_pattern = jobname_pattern


    def __call__(self, kernel_list):
        """
        Schedule jobs to run on the given list of kernel versions using
        the configured machines -> machine_info mapping for control file
        selection and kernel config file selection.
        """
        for kernel in kernel_list:
            # Get a list of all the machines available for testing
            # and the tests that each one is to execute and group them by
            # control/kernel-config so we can run a single job for the same
            # group

            # dictionary of (control-file,kernel-config)-><list-of-machines>
            jobs = {}
            for machine, info in self._control_map.iteritems():
                config_paths = info.kernel_configs
                kernel_config = '/boot/config'

                if config_paths:
                    kvers = config_paths.keys()
                    close =  self._closest_kver_leq(kvers, kernel)
                    kernel_config = config_paths[close]

                for control in info.control_files:
                    jobs.setdefault((control, kernel_config), [])
                    jobs[(control, kernel_config)].append(machine)

            for (control, kernel_config), hosts in jobs.iteritems():
                c = self._generate_control(control, kernel, kernel_config)
                self._schedule_job(self._jobname_pattern % kernel, c,
                                   hosts, control.endswith('.srv'))


    @classmethod
    def _kver_encode(cls, version):
        """
        Encode the various kernel version strings (ex 2.6.20, 2.6.21-rc1,
        2.7.30-rc2-git3, etc) in a way that makes them easily comparable using
        lexicographic ordering.

        @param version: kernel version string to encode

        @return processed kernel version string that can be compared using
                lexicographic comparison
        """
        # if it's not a "rc" release, add a -rc99 so it orders at the end of
        # all other rc releases for the same base kernel version
        if 'rc' not in version:
            version += '-rc99'

        # if it's not a git snapshot add a -git99 so it orders at the end of
        # all other git snapshots for the same base kernel version
        if 'git' not in version:
            version += '-git99'

        # make all number sequences to be at least 2 in size (with a leading 0
        # if necessary)
        bits = cls._encode_sep.split(version)
        for n in range(0, len(bits), 2):
            if len(bits[n]) < 2:
                bits[n] = '0' + bits[n]
        return ''.join(bits)


    @classmethod
    def _kver_cmp(cls, a, b):
        """
        Compare 2 kernel versions.

        @param a, b: kernel version strings to compare

        @return True if 'a' is less than 'b' or False otherwise
        """
        a, b = cls._kver_encode(a), cls._kver_encode(b)
        return cmp(a, b)


    @classmethod
    def _closest_kver_leq(cls, klist, kver):
        """
        Return the closest kernel ver in the list that is <= kver unless
        kver is the lowest, in which case return the lowest in klist.
        """
        if kver in klist:
            return kver
        l = list(klist)
        l.append(kver)
        l.sort(cmp=cls._kver_cmp)
        i = l.index(kver)
        if i == 0:
            return l[1]
        return l[i - 1]


    def _generate_control(self, control, kernel, kernel_config):
        """
        Wraps a given control file with the proper code to run it on a given
        kernel version.

        @param control: A str filename of the control file to wrap as a
                kernel test or an open file to the same
        @param kernel: A str of the kernel version (i.e. x.x.xx)
        @param kernel_config: A str filename to the kernel config on the
                client

        @returns a string of the generated control file
        """
        # Create the control file in a string
        c = ''

        c += self._PREAMBLE % (repr(kernel),
                               repr(os.path.expanduser(kernel_config)))

        is_autoserv_ctl = control.endswith('.srv')
        if not is_autoserv_ctl:
            c += self._AUTOTEST_WRAPPER

        # Open the basis control file and pull its contents into this one
        control = open(os.path.expanduser(control), 'r')

        # If is an AT file then we need to indent to match wrapper
        # function level indentation, srv files don't need this indentation
        indent = (4 * ' ', '')[is_autoserv_ctl]
        for line in control:
            c += '%s%s' % (indent, line)

        return c


    @staticmethod
    def _schedule_job(jobname, control, hosts, is_server_test):
        control_type = ('Client', 'Server')[is_server_test]

        afe = frontend.AFE()
        afe.create_job(control, jobname, control_type=control_type, hosts=hosts)


class email_action(base_action):
    """
    An action object to send emails about found new kernel versions.
    """
    _MAIL = 'sendmail'

    def __init__(self, dest_addr, from_addr='autotest-server@localhost'):
        """
        Create an email_action instance.

        @param dest_addr: a string or a list of strings with the destination
                email address(es)
        @param from_addr: optional source email address for the sent mails
                (default 'autotest-server@localhost')
        """
        # if passed a string for the dest_addr convert it to a tuple
        if type(dest_addr) is str:
            self._dest_addr = (dest_addr,)
        else:
            self._dest_addr = dest_addr

        self._from_addr = from_addr


    def __call__(self, kernel_list):
        if not kernel_list:
            return

        message = '\n'.join(kernel_list)
        message = 'Testing new kernel releases:\n%s' % message

        self._mail('autotest new kernel notification', message)


    def _mail(self, subject, message_text):
        message = email.Message.Message()
        message['To'] = ', '.join(self._dest_addr)
        message['From'] = self._from_addr
        message['Subject'] = subject
        message.set_payload(message_text)

        if self._sendmail(message.as_string()):
            server = smtplib.SMTP('localhost')
            try:
                server.sendmail(self._from_addr, self._dest_addr,
                                message.as_string())
            finally:
                server.quit()


    @classmethod
    def _sendmail(cls, message):
        """
        Send an email using the sendmail command.
        """
        # open a pipe to the mail program and
        # write the data to the pipe
        p = os.popen('%s -t' % cls._MAIL, 'w')
        p.write(message)
        return p.close()
