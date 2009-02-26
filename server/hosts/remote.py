"""This class defines the Remote host class, mixing in the SiteHost class
if it is available."""

import os, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import utils, profiler
from autotest_lib.server.hosts import base_classes, bootloader


class RemoteHost(base_classes.Host):
    """
    This class represents a remote machine on which you can run
    programs.

    It may be accessed through a network, a serial line, ...
    It is not the machine autoserv is running on.

    Implementation details:
    This is an abstract class, leaf subclasses must implement the methods
    listed here and in parent classes which have no implementation. They
    may reimplement methods which already have an implementation. You
    must not instantiate this class but should instantiate one of those
    leaf subclasses.
    """

    DEFAULT_REBOOT_TIMEOUT = base_classes.Host.DEFAULT_REBOOT_TIMEOUT
    LAST_BOOT_TAG = object()

    def _initialize(self, hostname, autodir=None, *args, **dargs):
        super(RemoteHost, self)._initialize(*args, **dargs)

        self.hostname = hostname
        self.autodir = autodir
        self.tmp_dirs = []


    def close(self):
        super(RemoteHost, self).close()
        self.stop_loggers()

        if hasattr(self, 'tmp_dirs'):
            for dir in self.tmp_dirs:
                try:
                    self.run('rm -rf "%s"' % (utils.sh_escape(dir)))
                except error.AutoservRunError:
                    pass


    def job_start(self):
        """
        Abstract method, called the first time a remote host object
        is created for a specific host after a job starts.

        This method depends on the create_host factory being used to
        construct your host object. If you directly construct host objects
        you will need to call this method yourself (and enforce the
        single-call rule).
        """
        pass


    def get_autodir(self):
        return self.autodir


    def set_autodir(self, autodir):
        """
        This method is called to make the host object aware of the
        where autotest is installed. Called in server/autotest.py
        after a successful install
        """
        self.autodir = autodir


    def sysrq_reboot(self):
        self.run('echo b > /proc/sysrq-trigger &')


    def reboot(self, timeout=DEFAULT_REBOOT_TIMEOUT, label=LAST_BOOT_TAG,
               kernel_args=None, wait=True, **dargs):
        """
        Reboot the remote host.

        Args:
                timeout - How long to wait for the reboot.
                label - The label we should boot into.  If None, we will
                        boot into the default kernel.  If it's LAST_BOOT_TAG,
                        we'll boot into whichever kernel was .boot'ed last
                        (or the default kernel if we haven't .boot'ed in this
                        job).  If it's None, we'll boot into the default kernel.
                        If it's something else, we'll boot into that.
                wait - Should we wait to see if the machine comes back up.
        """
        if self.job:
            if label == self.LAST_BOOT_TAG:
                label = self.job.last_boot_tag
            else:
                self.job.last_boot_tag = label

        self.reboot_setup(label=label, kernel_args=kernel_args, **dargs)

        if label or kernel_args:
            self.bootloader.install_boottool()
            if not label:
                default = int(self.bootloader.get_default())
                label = self.bootloader.get_titles()[default]
            self.bootloader.boot_once(label)
            if kernel_args:
                self.bootloader.add_args(label, kernel_args)

        # define a function for the reboot and run it in a group
        print "Reboot: initiating reboot"
        def reboot():
            self.record("GOOD", None, "reboot.start")
            try:
                # sync before starting the reboot, so that a long sync during
                # shutdown isn't timed out by wait_down's short timeout
                self.run('sync; sync', timeout=timeout, ignore_status=True)

                # Try several methods of rebooting in increasing harshness.
                self.run('('
                         ' sleep 5; reboot &'
                         ' sleep 60; reboot -f &'
                         ' sleep 10; reboot -nf &'
                         ' sleep 10; telinit 6 &'
                         ') </dev/null >/dev/null 2>&1 &')
            except error.AutoservRunError:
                self.record("ABORT", None, "reboot.start",
                              "reboot command failed")
                raise
            if wait:
                self.wait_for_restart(timeout, **dargs)

        # if this is a full reboot-and-wait, run the reboot inside a group
        if wait:
            self.log_reboot(reboot)
        else:
            reboot()


    def reboot_followup(self, *args, **dargs):
        super(RemoteHost, self).reboot_followup(*args, **dargs)
        if self.job:
            self.job.profilers.handle_reboot(self)


    def wait_for_restart(self, timeout=DEFAULT_REBOOT_TIMEOUT, **dargs):
        """
        Wait for the host to come back from a reboot. This wraps the
        generic wait_for_restart implementation in a reboot group.
        """
        def reboot_func():
            super(RemoteHost, self).wait_for_restart(timeout=timeout, **dargs)
        self.log_reboot(reboot_func)


    def cleanup(self):
        super(RemoteHost, self).cleanup()
        self.reboot()


    def get_tmp_dir(self, parent='/tmp'):
        """
        Return the pathname of a directory on the host suitable
        for temporary file storage.

        The directory and its content will be deleted automatically
        on the destruction of the Host object that was used to obtain
        it.
        """
        self.run("mkdir -p %s" % parent)
        template = os.path.join(parent, 'autoserv-XXXXXX')
        dir_name = self.run("mktemp -d %s" % template).stdout.rstrip()
        self.tmp_dirs.append(dir_name)
        return dir_name


    def ping(self):
        """
        Ping the remote system, and return whether it's available
        """
        fpingcmd = "%s -q %s" % ('/usr/bin/fping', self.hostname)
        rc = utils.system(fpingcmd, ignore_status = 1)
        return (rc == 0)


    def check_uptime(self):
        """
        Check that uptime is available and monotonically increasing.
        """
        if not self.ping():
            raise error.AutoservHostError('Client is not pingable')
        result = self.run("/bin/cat /proc/uptime", 30)
        return result.stdout.strip().split()[0]


    def get_crashinfo(self, test_start_time):
        print "Collecting crash information..."
        super(RemoteHost, self).get_crashinfo(test_start_time)

        # wait for four hours, to see if the machine comes back up
        current_time = time.strftime("%b %d %H:%M:%S", time.localtime())
        print "Waiting four hours for %s to come up (%s)" % (self.hostname,
                                                             current_time)
        if not self.wait_up(timeout=4*60*60):
            print "%s down, unable to collect crash info" % self.hostname
            return
        else:
            print "%s is back up, collecting crash info" % self.hostname

        # find a directory to put the crashinfo into
        if self.job:
            infodir = self.job.resultdir
        else:
            infodir = os.path.abspath(os.getcwd())
        infodir = os.path.join(infodir, "crashinfo.%s" % self.hostname)
        if not os.path.exists(infodir):
            os.mkdir(infodir)

        # collect various log files
        log_files = ["/var/log/messages", "/var/log/monitor-ssh-reboots"]
        for log in log_files:
            print "Collecting %s..." % log
            try:
                self.get_file(log, infodir)
            except Exception:
                print "Collection of %s failed. Non-fatal, continuing." % log

        # collect dmesg
        print "Collecting dmesg (saved to crashinfo/dmesg)..."
        devnull = open("/dev/null", "w")
        try:
            try:
                result = self.run("dmesg", stdout_tee=devnull).stdout
                file(os.path.join(infodir, "dmesg"), "w").write(result)
            except Exception, e:
                print "crashinfo collection of dmesg failed with:\n%s" % e
        finally:
            devnull.close()

        # collect any profiler data we can find
        print "Collecting any server-side profiler data lying around..."
        try:
            cmd = "ls %s" % profiler.PROFILER_TMPDIR
            profiler_dirs = [path for path in self.run(cmd).stdout.split()
                             if path.startswith("autoserv-")]
            for profiler_dir in profiler_dirs:
                remote_path = profiler.get_profiler_results_dir(profiler_dir)
                remote_exists = self.run("ls %s" % remote_path,
                                         ignore_status=True).exit_status == 0
                if not remote_exists:
                    continue
                local_path = os.path.join(infodir, "profiler." + profiler_dir)
                os.mkdir(local_path)
                self.get_file(remote_path + "/", local_path)
        except Exception, e:
            print "crashinfo collection of profiler data failed with:\n%s" % e


    def are_wait_up_processes_up(self):
        """
        Checks if any HOSTS waitup processes are running yet on the
        remote host.

        Returns True if any the waitup processes are running, False
        otherwise.
        """
        processes = self.get_wait_up_processes()
        if len(processes) == 0:
            return True # wait up processes aren't being used
        for procname in processes:
            exit_status = self.run("{ ps -e || ps; } | grep '%s'" % procname,
                                   ignore_status=True).exit_status
            if exit_status == 0:
                return True
        return False
