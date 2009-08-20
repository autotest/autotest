import re, os

from autotest_lib.client.common_lib import utils as common_utils
from autotest_lib.tko import utils as tko_utils, models, status_lib
from autotest_lib.tko.parsers import base


class NoHostnameError(Exception):
    pass


class job(models.job):
    def __init__(self, dir):
        job_dict = job.load_from_dir(dir)
        super(job, self).__init__(dir, **job_dict)


    @classmethod
    def load_from_dir(cls, dir):
        keyval = cls.read_keyval(dir)
        tko_utils.dprint(str(keyval))

        user = keyval.get("user", None)
        label = keyval.get("label", None)
        queued_time = tko_utils.get_timestamp(keyval, "job_queued")
        started_time = tko_utils.get_timestamp(keyval, "job_started")
        finished_time = tko_utils.get_timestamp(keyval, "job_finished")
        machine = cls.determine_hostname(keyval, dir)
        machine_group = cls.determine_machine_group(machine, dir)
        machine_owner = keyval.get("owner", None)

        aborted_by = keyval.get("aborted_by", None)
        aborted_at = tko_utils.get_timestamp(keyval, "aborted_on")

        return {"user": user, "label": label, "machine": machine,
                "queued_time": queued_time, "started_time": started_time,
                "finished_time": finished_time, "machine_owner": machine_owner,
                "machine_group": machine_group, "aborted_by": aborted_by,
                "aborted_on": aborted_at}


    @classmethod
    def determine_hostname(cls, keyval, job_dir):
        host_group_name = keyval.get("host_group_name", None)
        machine = keyval.get("hostname", "")
        is_multimachine = "," in machine

        # determine what hostname to use
        if host_group_name:
            if is_multimachine or not machine:
                tko_utils.dprint("Using host_group_name %r instead of "
                                 "machine name." % host_group_name)
                machine = host_group_name
        elif is_multimachine:
            try:
                machine = job.find_hostname(job_dir) # find a unique hostname
            except NoHostnameError:
                pass  # just use the comma-separated name

        tko_utils.dprint("MACHINE NAME: %s" % machine)
        return machine


    @classmethod
    def determine_machine_group(cls, hostname, job_dir):
        machine_groups = set()
        for individual_hostname in hostname.split(","):
            host_keyval = models.test.parse_host_keyval(job_dir,
                                                        individual_hostname)
            if not host_keyval:
                tko_utils.dprint('Unable to parse host keyval for %s'
                                 % individual_hostname)
            elif "platform" in host_keyval:
                machine_groups.add(host_keyval["platform"])
        machine_group = ",".join(sorted(machine_groups))
        tko_utils.dprint("MACHINE GROUP: %s" % machine_group)
        return machine_group


    @staticmethod
    def find_hostname(path):
        hostname = os.path.join(path, "sysinfo", "hostname")
        try:
            machine = open(hostname).readline().rstrip()
            return machine
        except Exception:
            tko_utils.dprint("Could not read a hostname from "
                             "sysinfo/hostname")

        uname = os.path.join(path, "sysinfo", "uname_-a")
        try:
            machine = open(uname).readline().split()[1]
            return machine
        except Exception:
            tko_utils.dprint("Could not read a hostname from "
                             "sysinfo/uname_-a")

        raise NoHostnameError("Unable to find a machine name")


class kernel(models.kernel):
    def __init__(self, job, verify_ident=None):
        kernel_dict = kernel.load_from_dir(job.dir, verify_ident)
        super(kernel, self).__init__(**kernel_dict)


    @staticmethod
    def load_from_dir(dir, verify_ident=None):
        # try and load the booted kernel version
        attributes = False
        i = 1
        build_dir = os.path.join(dir, "build")
        while True:
            if not os.path.exists(build_dir):
                break
            build_log = os.path.join(build_dir, "debug", "build_log")
            attributes = kernel.load_from_build_log(build_log)
            if attributes:
                break
            i += 1
            build_dir = os.path.join(dir, "build.%d" % (i))

        if not attributes:
            if verify_ident:
                base = verify_ident
            else:
                base = kernel.load_from_sysinfo(dir)
            patches = []
            hashes = []
        else:
            base, patches, hashes = attributes
        tko_utils.dprint("kernel.__init__() found kernel version %s"
                         % base)

        # compute the kernel hash
        if base == "UNKNOWN":
            kernel_hash = "UNKNOWN"
        else:
            kernel_hash = kernel.compute_hash(base, hashes)

        return {"base": base, "patches": patches,
                "kernel_hash": kernel_hash}


    @staticmethod
    def load_from_sysinfo(path):
        for subdir in ("reboot1", ""):
            uname_path = os.path.join(path, "sysinfo", subdir,
                                      "uname_-a")
            if not os.path.exists(uname_path):
                continue
            uname = open(uname_path).readline().split()
            return re.sub("-autotest$", "", uname[2])
        return "UNKNOWN"


    @staticmethod
    def load_from_build_log(path):
        if not os.path.exists(path):
            return None

        base, patches, hashes = "UNKNOWN", [], []
        for line in file(path):
            head, rest = line.split(": ", 1)
            rest = rest.split()
            if head == "BASE":
                base = rest[0]
            elif head == "PATCH":
                patches.append(patch(*rest))
                hashes.append(rest[2])
        return base, patches, hashes


class test(models.test):
    def __init__(self, subdir, testname, status, reason, test_kernel,
                 machine, started_time, finished_time, iterations,
                 attributes):
        # for backwards compatibility with the original parser
        # implementation, if there is no test version we need a NULL
        # value to be used; also, if there is a version it should
        # be terminated by a newline
        if "version" in attributes:
            attributes["version"] = str(attributes["version"])
        else:
            attributes["version"] = None

        super(test, self).__init__(subdir, testname, status, reason,
                                   test_kernel, machine, started_time,
                                   finished_time, iterations,
                                   attributes)


    @staticmethod
    def load_iterations(keyval_path):
        return iteration.load_from_keyval(keyval_path)


class patch(models.patch):
    def __init__(self, spec, reference, hash):
        tko_utils.dprint("PATCH::%s %s %s" % (spec, reference, hash))
        super(patch, self).__init__(spec, reference, hash)
        self.spec = spec
        self.reference = reference
        self.hash = hash


class iteration(models.iteration):
    @staticmethod
    def parse_line_into_dicts(line, attr_dict, perf_dict):
        key, value = line.split("=", 1)
        perf_dict[key] = value


class status_line(object):
    def __init__(self, indent, status, subdir, testname, reason,
                 optional_fields):
        # pull out the type & status of the line
        if status == "START":
            self.type = "START"
            self.status = None
        elif status.startswith("END "):
            self.type = "END"
            self.status = status[4:]
        else:
            self.type = "STATUS"
            self.status = status
        assert (self.status is None or
                self.status in status_lib.statuses)

        # save all the other parameters
        self.indent = indent
        self.subdir = self.parse_name(subdir)
        self.testname = self.parse_name(testname)
        self.reason = reason
        self.optional_fields = optional_fields


    @staticmethod
    def parse_name(name):
        if name == "----":
            return None
        return name


    @staticmethod
    def is_status_line(line):
        return re.search(r"^\t*(\S[^\t]*\t){3}", line) is not None


    @classmethod
    def parse_line(cls, line):
        if not status_line.is_status_line(line):
            return None
        indent, line = re.search(r"^(\t*)(.*)$", line).groups()
        indent = len(indent)

        # split the line into the fixed and optional fields
        parts = line.split("\t")
        status, subdir, testname = parts[0:3]
        reason = parts[-1]
        optional_parts = parts[3:-1]

        # all the optional parts should be of the form "key=value"
        assert sum('=' not in part for part in optional_parts) == 0
        optional_fields = dict(part.split("=", 1)
                               for part in optional_parts)

        # build up a new status_line and return it
        return cls(indent, status, subdir, testname, reason,
                   optional_fields)


class parser(base.parser):
    @staticmethod
    def make_job(dir):
        return job(dir)


    def state_iterator(self, buffer):
        new_tests = []
        boot_count = 0
        group_subdir = None
        sought_level = 0
        stack = status_lib.status_stack()
        current_kernel = kernel(self.job)
        boot_in_progress = False
        alert_pending = None
        started_time = None

        while not self.finished or buffer.size():
            # stop processing once the buffer is empty
            if buffer.size() == 0:
                yield new_tests
                new_tests = []
                continue

            # parse the next line
            line = buffer.get()
            tko_utils.dprint('\nSTATUS: ' + line.strip())
            line = status_line.parse_line(line)
            if line is None:
                tko_utils.dprint('non-status line, ignoring')
                continue # ignore non-status lines

            # have we hit the job start line?
            if (line.type == "START" and not line.subdir and
                not line.testname):
                sought_level = 1
                tko_utils.dprint("found job level start "
                                 "marker, looking for level "
                                 "1 groups now")
                continue

            # have we hit the job end line?
            if (line.type == "END" and not line.subdir and
                not line.testname):
                tko_utils.dprint("found job level end "
                                 "marker, looking for level "
                                 "0 lines now")
                sought_level = 0

            # START line, just push another layer on to the stack
            # and grab the start time if this is at the job level
            # we're currently seeking
            if line.type == "START":
                group_subdir = None
                stack.start()
                if line.indent == sought_level:
                    started_time = \
                                 tko_utils.get_timestamp(
                        line.optional_fields, "timestamp")
                tko_utils.dprint("start line, ignoring")
                continue
            # otherwise, update the status on the stack
            else:
                tko_utils.dprint("GROPE_STATUS: %s" %
                                 [stack.current_status(),
                                  line.status, line.subdir,
                                  line.testname, line.reason])
                stack.update(line.status)

            if line.status == "ALERT":
                tko_utils.dprint("job level alert, recording")
                alert_pending = line.reason
                continue

            # ignore Autotest.install => GOOD lines
            if (line.testname == "Autotest.install" and
                line.status == "GOOD"):
                tko_utils.dprint("Successful Autotest "
                                 "install, ignoring")
                continue

            # ignore END lines for a reboot group
            if (line.testname == "reboot" and line.type == "END"):
                tko_utils.dprint("reboot group, ignoring")
                continue

            # convert job-level ABORTs into a 'CLIENT_JOB' test, and
            # ignore other job-level events
            if line.testname is None:
                if (line.status == "ABORT" and
                    line.type != "END"):
                    line.testname = "CLIENT_JOB"
                else:
                    tko_utils.dprint("job level event, "
                                    "ignoring")
                    continue

            # use the group subdir for END lines
            if line.type == "END":
                line.subdir = group_subdir

            # are we inside a block group?
            if (line.indent != sought_level and
                line.status != "ABORT" and
                not line.testname.startswith('reboot.')):
                if line.subdir:
                    tko_utils.dprint("set group_subdir: "
                                     + line.subdir)
                    group_subdir = line.subdir
                tko_utils.dprint("ignoring incorrect indent "
                                 "level %d != %d," %
                                 (line.indent, sought_level))
                continue

            # use the subdir as the testname, except for
            # boot.* and kernel.* tests
            if (line.testname is None or
                not re.search(r"^(boot(\.\d+)?$|kernel\.)",
                              line.testname)):
                if line.subdir and '.' in line.subdir:
                    line.testname = line.subdir

            # has a reboot started?
            if line.testname == "reboot.start":
                started_time = tko_utils.get_timestamp(
                    line.optional_fields, "timestamp")
                tko_utils.dprint("reboot start event, "
                                 "ignoring")
                boot_in_progress = True
                continue

            # has a reboot finished?
            if line.testname == "reboot.verify":
                line.testname = "boot.%d" % boot_count
                tko_utils.dprint("reboot verified")
                boot_in_progress = False
                verify_ident = line.reason.strip()
                current_kernel = kernel(self.job, verify_ident)
                boot_count += 1

            if alert_pending:
                line.status = "ALERT"
                line.reason = alert_pending
                alert_pending = None

            # create the actual test object
            finished_time = tko_utils.get_timestamp(
                line.optional_fields, "timestamp")
            final_status = stack.end()
            tko_utils.dprint("Adding: "
                             "%s\nSubdir:%s\nTestname:%s\n%s" %
                             (final_status, line.subdir,
                              line.testname, line.reason))
            new_test = test.parse_test(self.job, line.subdir,
                                       line.testname,
                                       final_status, line.reason,
                                       current_kernel,
                                       started_time,
                                       finished_time)
            started_time = None
            new_tests.append(new_test)

        # the job is finished, but we never came back from reboot
        if boot_in_progress:
            testname = "boot.%d" % boot_count
            reason = "machine did not return from reboot"
            tko_utils.dprint(("Adding: ABORT\nSubdir:----\n"
                              "Testname:%s\n%s")
                             % (testname, reason))
            new_test = test.parse_test(self.job, None, testname,
                                       "ABORT", reason,
                                       current_kernel, None, None)
            new_tests.append(new_test)
        yield new_tests
