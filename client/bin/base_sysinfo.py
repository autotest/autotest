import os, shutil, re, glob, subprocess

from autotest_lib.client.common_lib import utils, log


_DEFAULT_COMMANDS_TO_LOG_PER_TEST = []
_DEFAULT_COMMANDS_TO_LOG_PER_BOOT = [
    "lspci -vvn", "gcc --version", "ld --version", "mount", "hostname",
    "uptime",
    ]

_DEFAULT_FILES_TO_LOG_PER_TEST = []
_DEFAULT_FILES_TO_LOG_PER_BOOT = [
    "/proc/pci", "/proc/meminfo", "/proc/slabinfo", "/proc/version",
    "/proc/cpuinfo", "/proc/modules", "/proc/interrupts",
    ]


class loggable(object):
    """ Abstract class for representing all things "loggable" by sysinfo. """
    def __init__(self, log_in_keyval):
        self.log_in_keyval = log_in_keyval


    def readline(self, logdir):
        path = os.path.join(logdir, self.logfile)
        if os.path.exists(path):
            return utils.read_one_line(path)
        else:
            return ""


class logfile(loggable):
    def __init__(self, path, log_in_keyval=False):
        super(logfile, self).__init__(log_in_keyval)
        self.path = path
        self.logfile = os.path.basename(self.path)


    def __repr__(self):
        return "sysinfo.logfile(%r, %r)" % (self.path, self.log_in_keyval)


    def __eq__(self, other):
        if isinstance(other, logfile):
            return self.path == other.path
        elif isinstance(other, loggable):
            return False
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


    def __hash__(self):
        return hash(self.path)


    def run(self, logdir):
        if os.path.exists(self.path):
            shutil.copy(self.path, logdir)


class command(loggable):
    def __init__(self, cmd, logfile=None, log_in_keyval=False):
        super(command, self).__init__(log_in_keyval)
        self.cmd = cmd
        if logfile:
            self.logfile = logfile
        else:
            self.logfile = cmd.replace(" ", "_")


    def __repr__(self):
        r = "sysinfo.command(%r, %r, %r)"
        r %= (self.cmd, self.logfile, self.log_in_keyval)
        return r


    def __eq__(self, other):
        if isinstance(other, command):
            return (self.cmd, self.logfile) == (other.cmd, other.logfile)
        elif isinstance(other, loggable):
            return False
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


    def __hash__(self):
        return hash((self.cmd, self.logfile))


    def run(self, logdir):
        stdin = open(os.devnull, "r")
        stdout = open(os.path.join(logdir, self.logfile), "w")
        stderr = open(os.devnull, "w")
        env = os.environ.copy()
        if "PATH" not in env:
            env["PATH"] = "/usr/bin:/bin"
        subprocess.call(self.cmd, stdin=stdin, stdout=stdout, stderr=stderr,
                        shell=True, env=env)
        for f in (stdin, stdout, stderr):
            f.close()


class base_sysinfo(object):
    def __init__(self, job_resultsdir):
        self.sysinfodir = self._get_sysinfodir(job_resultsdir)

        # pull in the post-test logs to collect
        self.test_loggables = set()
        for cmd in _DEFAULT_COMMANDS_TO_LOG_PER_TEST:
            self.test_loggables.add(command(cmd))
        for filename in _DEFAULT_FILES_TO_LOG_PER_TEST:
            self.test_loggables.add(logfile(filename))

        # pull in the EXTRA post-boot logs to collect
        self.boot_loggables = set()
        for cmd in _DEFAULT_COMMANDS_TO_LOG_PER_BOOT:
            self.boot_loggables.add(command(cmd))
        for filename in _DEFAULT_FILES_TO_LOG_PER_BOOT:
            self.boot_loggables.add(logfile(filename))

        # add in a couple of extra files and commands we want to grab
        self.test_loggables.add(command("df -mP", logfile="df"))
        self.test_loggables.add(command("dmesg -c", logfile="dmesg"))
        self.boot_loggables.add(logfile("/proc/cmdline",
                                             log_in_keyval=True))
        self.boot_loggables.add(command("uname -a", logfile="uname",
                                             log_in_keyval=True))


    def serialize(self):
        return {"boot": self.boot_loggables, "test": self.test_loggables}


    def deserialize(self, serialized):
        self.boot_loggables = serialized["boot"]
        self.test_loggables = serialized["test"]


    @staticmethod
    def _get_sysinfodir(resultsdir):
        sysinfodir = os.path.join(resultsdir, "sysinfo")
        if not os.path.exists(sysinfodir):
            os.makedirs(sysinfodir)
        return sysinfodir


    def _get_reboot_count(self):
        if not glob.glob(os.path.join(self.sysinfodir, "*")):
            return -1
        else:
            return len(glob.glob(os.path.join(self.sysinfodir, "boot.*")))


    def _get_boot_subdir(self, next=False):
        reboot_count = self._get_reboot_count()
        if next:
            reboot_count += 1
        if reboot_count < 1:
            return self.sysinfodir
        else:
            boot_dir = "boot.%d" % (reboot_count - 1)
            return os.path.join(self.sysinfodir, boot_dir)


    @log.log_and_ignore_errors("post-reboot sysinfo error:")
    def log_per_reboot_data(self):
        """ Logging hook called whenever a job starts, and again after
        any reboot. """
        logdir = self._get_boot_subdir(next=True)
        if not os.path.exists(logdir):
            os.mkdir(logdir)

        for log in (self.test_loggables | self.boot_loggables):
            log.run(logdir)


    @log.log_and_ignore_errors("pre-test sysinfo error:")
    def log_before_each_test(self, test):
        """ Logging hook called before a test starts. """
        if os.path.exists("/var/log/messages"):
            stat = os.stat("/var/log/messages")
            self._messages_size = stat.st_size
            self._messages_inode = stat.st_ino


    @log.log_and_ignore_errors("post-test sysinfo error:")
    def log_after_each_test(self, test):
        """ Logging hook called after a test finishs. """
        test_sysinfodir = self._get_sysinfodir(test.outputdir)

        # create a symlink in the test sysinfo dir to the current boot
        reboot_dir = self._get_boot_subdir()
        assert os.path.exists(reboot_dir)
        symlink_dest = os.path.join(test_sysinfodir, "reboot_current")
        os.symlink(reboot_dir, symlink_dest)

        # run all the standard logging commands
        for log in self.test_loggables:
            log.run(test_sysinfodir)

        # grab any new data from /var/log/messages
        self._log_messages(test_sysinfodir)

        # log some sysinfo data into the test keyval file
        keyval = self.log_test_keyvals(test_sysinfodir)
        test.write_test_keyval(keyval)


    def _log_messages(self, logdir):
        """ Log all of the new data in /var/log/messages. """
        try:
            # log all of the new data in /var/log/messages
            bytes_to_skip = 0
            if hasattr(self, "_messages_size"):
                current_inode = os.stat("/var/log/messages").st_ino
                if current_inode == self._messages_inode:
                    bytes_to_skip = self._messages_size
            in_messages = open("/var/log/messages")
            in_messages.seek(bytes_to_skip)
            out_messages = open(os.path.join(logdir, "messages"), "w")
            out_messages.write(in_messages.read())
            in_messages.close()
            out_messages.close()
        except Exception, e:
            print "/var/log/messages collection failed with %s" % e


    @staticmethod
    def _read_sysinfo_keyvals(loggables, logdir):
        keyval = {}
        for log in loggables:
            if log.log_in_keyval:
                keyval["sysinfo-" + log.logfile] = log.readline(logdir)
        return keyval


    def log_test_keyvals(self, test_sysinfodir):
        """ Logging hook called by log_after_each_test to collect keyval
        entries to be written in the test keyval. """
        keyval = {}

        # grab any loggables that should be in the keyval
        keyval.update(self._read_sysinfo_keyvals(
            self.test_loggables, test_sysinfodir))
        keyval.update(self._read_sysinfo_keyvals(
            self.boot_loggables,
            os.path.join(test_sysinfodir, "reboot_current")))

        # remove hostname from uname info
        #   Linux lpt36 2.6.18-smp-230.1 #1 [4069269] SMP Fri Oct 24 11:30:...
        if "sysinfo-uname" in keyval:
            kernel_vers = " ".join(keyval["sysinfo-uname"].split()[2:])
            keyval["sysinfo-uname"] = kernel_vers

        # grab the total memory
        path = os.path.join(test_sysinfodir, "reboot_current", "meminfo")
        if os.path.exists(path):
            mem_data = open(path).read()
            match = re.search(r"^MemTotal:\s+(\d+) kB$", mem_data,
                              re.MULTILINE)
            if match:
                keyval["sysinfo-memtotal-in-kb"] = match.group(1)

        # return what we collected
        return keyval
