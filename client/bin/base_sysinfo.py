import os, shutil, re, glob, subprocess

from autotest_lib.client.common_lib import utils, log


class command(object):
    def __init__(self, cmd, logfile=None):
        self.cmd = cmd
        if logfile:
            self.logfile = logfile
        else:
            self.logfile = cmd.replace(" ", "_")


    def __eq__(self, other):
        if isinstance(other, command):
            return (self.cmd, self.logfile) == (other.cmd, other.logfile)
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


    @classmethod
    def get_postboot_log_files(cls):
        return set(["/proc/pci", "/proc/meminfo", "/proc/slabinfo",
                    "/proc/version", "/proc/cpuinfo", "/proc/cmdline",
                    "/proc/modules", "/proc/interrupts"])


    @classmethod
    def get_posttest_log_commands(cls):
        return set([command("dmesg -c", "dmesg"), command("df -mP", "df")])


    @classmethod
    def get_postboot_log_commands(cls):
        commands = cls.get_posttest_log_commands()
        commands |= set([command("uname -a"), command("lspci -vvn"),
                         command("gcc --version"), command("ld --version"),
                         command("mount"), command("hostname")])
        return commands


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
        """ Log this data when the job starts, and again after any reboot. """
        logdir = self._get_boot_subdir(next=True)
        if not os.path.exists(logdir):
            os.mkdir(logdir)

        # run all the standard logging commands
        for cmd in self.get_postboot_log_commands():
            cmd.run(logdir)

        # grab all the standard logging files
        for filename in self.get_postboot_log_files():
            if os.path.exists(filename):
                shutil.copy(filename, logdir)


    @log.log_and_ignore_errors("pre-test sysinfo error:")
    def log_before_each_test(self, test):
        if os.path.exists("/var/log/messages"):
            stat = os.stat("/var/log/messages")
            self._messages_size = stat.st_size
            self._messages_inode = stat.st_ino


    @log.log_and_ignore_errors("post-test sysinfo error:")
    def log_after_each_test(self, test):
        test_sysinfodir = self._get_sysinfodir(test.outputdir)

        # create a symlink in the test sysinfo dir to the current boot
        reboot_dir = self._get_boot_subdir()
        assert os.path.exists(reboot_dir)
        symlink_dest = os.path.join(test_sysinfodir, "reboot_current")
        os.symlink(reboot_dir, symlink_dest)

        # run all the standard logging commands
        for cmd in self.get_posttest_log_commands():
            cmd.run(test_sysinfodir)

        # grab any new data from /var/log/messages
        self._log_messages(test_sysinfodir)

        # log some sysinfo data into the test keyval file
        self._log_test_keyvals(test)


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


    def _log_test_keyvals(self, test):
        keyval = {}
        test_sysinfodir = self._get_sysinfodir(test.outputdir)

        # grab a bunch of single line files and turn them into keyvals
        files_to_log = ["cmdline", "uname_-a"]
        keyval_fields = ["cmdline", "uname"]
        for filename, field in zip(files_to_log, keyval_fields):
            path = os.path.join(test_sysinfodir, "reboot_current", filename)
            if os.path.exists(path):
                keyval["sysinfo-%s" % field] = utils.read_one_line(path)

        # grab the total memory
        path = os.path.join(test_sysinfodir, "reboot_current", "meminfo")
        if os.path.exists(path):
            mem_data = open(path).read()
            match = re.search(r"^MemTotal:\s+(\d+) kB$", mem_data,
                              re.MULTILINE)
            if match:
                keyval["sysinfo-memtotal-in-kb"] = match.group(1)

        # write out the data to the test keyval file
        test.write_test_keyval(keyval)
