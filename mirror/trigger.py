import email
import os
import re
import smtplib

from autotest.server import frontend


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

        :param kernel_list: a sequence of kernel filenames (strings)
        """
        raise NotImplementedError('__call__ not implemented')


class map_action(base_action):

    """
    Action that uses a map between machines and their associated control
    files and kernel configuration files and it schedules them using
    the AFE.
    """

    _encode_sep = re.compile('(\D+)')

    class machine_info(object):

        """
        Class to organize the machine associated information for this action.
        """

        def __init__(self, tests, kernel_configs):
            """
            Instantiate a machine_info object.

            :param tests: a sequence of test names (as named in the frontend
                    database) to run for this host
            :param kernel_configs: a dictionary of
                    kernel_version -> config_filename associating kernel
                    versions with corresponding kernel configuration files
                    ("~" inside the filename will be expanded)
            """
            self.tests = tests
            self.kernel_configs = kernel_configs

    def __init__(self, tests_map, jobname_pattern, job_owner='autotest',
                 upload_kernel_config=False):
        """
        Instantiate a map_action.

        :param tests_map: a dictionary of hostname -> machine_info
        :param jobname_pattern: a string pattern used to make the job name
                containing a single "%s" that will be replaced with the kernel
                version
        :param job_owner: the user used to talk with the RPC server
        :param upload_kernel_config: specify if the generate control file
                should contain code that downloads and sends to the client the
                kernel config file (in case it is an URL); this requires that
                the tests_map refers only to server side tests
        """
        self._tests_map = tests_map
        self._jobname_pattern = jobname_pattern
        self._afe = frontend.AFE(user=job_owner)
        self._upload_kernel_config = upload_kernel_config

    def __call__(self, kernel_list):
        """
        Schedule jobs to run on the given list of kernel versions using
        the configured machines -> machine_info mapping for test name
        selection and kernel config file selection.
        """
        for kernel in kernel_list:
            # Get a list of all the machines available for testing
            # and the tests that each one is to execute and group them by
            # test/kernel-config so we can run a single job for the same
            # group

            # dictionary of (test-name,kernel-config)-><list-of-machines>
            jobs = {}
            for machine, info in self._tests_map.items():
                config_paths = info.kernel_configs
                kernel_config = '/boot/config'

                if config_paths:
                    kvers = config_paths.keys()
                    close = self._closest_kver_leq(kvers, kernel)
                    kernel_config = config_paths[close]

                for test in info.tests:
                    jobs.setdefault((test, kernel_config), [])
                    jobs[(test, kernel_config)].append(machine)

            for (test, kernel_config), hosts in jobs.items():
                c = self._generate_control(test, kernel, kernel_config)
                self._schedule_job(self._jobname_pattern % kernel, c, hosts)

    @classmethod
    def _kver_encode(cls, version):
        """
        Encode the various kernel version strings (ex 2.6.20, 2.6.21-rc1,
        2.7.30-rc2-git3, etc) in a way that makes them easily comparable using
        lexicographic ordering.

        :param version: kernel version string to encode

        :return: processed kernel version string that can be compared using
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

        :param a, b: kernel version strings to compare

        :return: True if 'a' is less than 'b' or False otherwise
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
        kversions = list(klist)
        kversions.append(kver)
        kversions.sort(cmp=cls._kver_cmp)
        i = kversions.index(kver)
        if i == 0:
            return kversions[1]
        return kversions[i - 1]

    def _generate_control(self, test, kernel, kernel_config):
        """
        Uses generate_control_file RPC to generate a control file given
        a test name and kernel information.

        :param test: The test name string as it's named in the frontend
                database.
        :param kernel: A str of the kernel version (i.e. x.x.xx)
        :param kernel_config: A str filename to the kernel config on the
                client

        :return: a dict representing a control file as described by
                frontend.afe.rpc_interface.generate_control_file
        """
        kernel_info = dict(version=kernel,
                           config_file=os.path.expanduser(kernel_config))
        return self._afe.generate_control_file(
            tests=[test], kernel=[kernel_info],
            upload_kernel_config=self._upload_kernel_config)

    def _schedule_job(self, jobname, control, hosts):
        control_type = ('Client', 'Server')[control.is_server]

        self._afe.create_job(control.control_file, jobname,
                             control_type=control_type, hosts=hosts)


class email_action(base_action):

    """
    An action object to send emails about found new kernel versions.
    """
    _MAIL = 'sendmail'

    def __init__(self, dest_addr, from_addr='autotest-server@localhost'):
        """
        Create an email_action instance.

        :param dest_addr: a string or a list of strings with the destination
                email address(es)
        :param from_addr: optional source email address for the sent mails
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
