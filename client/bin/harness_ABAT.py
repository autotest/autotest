"""The ABAT harness interface

The interface as required for ABAT.
"""

__author__ = """Copyright Andy Whitcroft 2006"""

from autotest_lib.client.bin import utils
import os, harness, time, re

def autobench_load(fn):
    disks = re.compile(r'^\s*DATS_FREE_DISKS\s*=(.*\S)\s*$')
    parts = re.compile(r'^\s*DATS_FREE_PARTITIONS\s*=(.*\S)\s*$')
    modules = re.compile(r'^\s*INITRD_MODULES\s*=(.*\S)\s*$')

    conf = {}

    try:
        fd = file(fn, "r")
    except:
        return conf
    for ln in fd.readlines():
        m = disks.match(ln)
        if m:
            val = m.groups()[0]
            conf['disks'] = val.strip('"').split()
        m = parts.match(ln)
        if m:
            val = m.groups()[0]
            conf['partitions'] = val.strip('"').split()
        m = modules.match(ln)
        if m:
            val = m.groups()[0]
            conf['modules'] = val.strip('"').split()
    fd.close()

    return conf


class harness_ABAT(harness.harness):
    """The ABAT server harness

    Properties:
            job
                    The job object for this job
    """

    def __init__(self, job, harness_args):
        """
                job
                        The job object for this job
        """
        self.setup(job)

        if 'ABAT_STATUS' in os.environ:
            self.status = file(os.environ['ABAT_STATUS'], "w")
        else:
            self.status = None


    def __send(self, msg):
        if self.status:
            msg = msg.rstrip()
            self.status.write(msg + "\n")
            self.status.flush()


    def __send_status(self, code, subdir, operation, msg):
        self.__send("STATUS %s %s %s %s" % (code, subdir, operation, msg))


    def __root_device(self):
        device = None
        root = re.compile(r'^\S*(/dev/\S+).*\s/\s*$')

        df = utils.system_output('df -lP')
        for line in df.split("\n"):
            m = root.match(line)
            if m:
                device = m.groups()[0]

        return device


    def run_start(self):
        """A run within this job is starting"""
        self.__send_status('GOOD', '----', '----', 'run starting')

        # Load up the autobench.conf if it exists.
        conf = autobench_load("/etc/autobench.conf")
        if 'partitions' in conf:
            self.job.config_set('partition.partitions',
                    conf['partitions'])

        # Search the boot loader configuration for the autobench entry,
        # and extract its args.
        args = None
        for entry in self.job.bootloader.get_entries().itervalues():
            if entry['title'].startswith('autobench'):
                args = entry.get('args')

        if args:
            args = re.sub(r'autobench_args:.*', '', args)
            args = re.sub(r'root=\S*', '', args)
            args += " root=" + self.__root_device()

            self.job.config_set('boot.default_args', args)

        # Turn off boot_once semantics.
        self.job.config_set('boot.set_default', True)

        # For RedHat installs we do not load up the module.conf
        # as they cannot be builtin.  Pass them as arguments.
        vendor = utils.get_os_vendor()
        if vendor in ['Red Hat', 'Fedora Core'] and 'modules' in conf:
            args = '--allow-missing'
            for mod in conf['modules']:
                args += " --with " + mod
            self.job.config_set('kernel.mkinitrd_extra_args', args)


    def run_reboot(self):
        """A run within this job is performing a reboot
           (expect continue following reboot)
        """
        self.__send("REBOOT")


    def run_complete(self):
        """A run within this job is completing (all done)"""
        self.__send("DONE")


    def test_status_detail(self, code, subdir, operation, msg, tag,
                           optional_fields):
        """A test within this job is completing (detail)"""

        # Send the first line with the status code as a STATUS message.
        lines = msg.split("\n")
        self.__send_status(code, subdir, operation, lines[0])


    def test_status(self, msg, tag):
        lines = msg.split("\n")

        # Send each line as a SUMMARY message.
        for line in lines:
            self.__send("SUMMARY :" + line)
