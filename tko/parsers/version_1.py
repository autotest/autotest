import os, re, time

from autotest_lib.tko import models, status_lib, utils as tko_utils
from autotest_lib.tko.parsers import base, version_0


class job(version_0.job):
    def exit_status(self):
        # find the .autoserv_execute path
        top_dir = tko_utils.find_toplevel_job_dir(self.dir)
        if not top_dir:
            return "ABORT"
        execute_path = os.path.join(top_dir, ".autoserv_execute")

        # if for some reason we can't read the status code, assume disaster
        if not os.path.exists(execute_path):
            return "ABORT"
        lines = open(execute_path).readlines()
        if len(lines) < 2:
            return "ABORT"
        try:
            status_code = int(lines[1])
        except ValueError:
            return "ABORT"

        if not os.WIFEXITED(status_code):
            # looks like a signal - an ABORT
            return "ABORT"
        elif os.WEXITSTATUS(status_code) != 0:
            # looks like a non-zero exit - a failure
            return "FAIL"
        else:
            # looks like exit code == 0
            return "GOOD"


class kernel(models.kernel):
    def __init__(self, base, patches):
        if base:
            patches = [patch(*p.split()) for p in patches]
            hashes = [p.hash for p in patches]
            kernel_hash = self.compute_hash(base, hashes)
        else:
            base = "UNKNOWN"
            patches = []
            kernel_hash = "UNKNOWN"
        super(kernel, self).__init__(base, patches, kernel_hash)


class test(models.test):
    @staticmethod
    def load_iterations(keyval_path):
        return iteration.load_from_keyval(keyval_path)


class iteration(models.iteration):
    @staticmethod
    def parse_line_into_dicts(line, attr_dict, perf_dict):
        key, val_type, value = "", "", ""

        # figure out what the key, value and keyval type are
        typed_match = re.search("^([^=]*)\{(\w*)\}=(.*)$", line)
        if typed_match:
            key, val_type, value = typed_match.groups()
        else:
            # old-fashioned untyped match, assume perf
            untyped_match = re.search("^([^=]*)=(.*)$", line)
            if untyped_match:
                key, value = untyped_match.groups()
                val_type = "perf"

        # parse the actual value into a dict
        if val_type == "attr":
            attr_dict[key] = value
        elif val_type == "perf" and re.search("^\d+(\.\d+)?$", value):
            perf_dict[key] = float(value)
        else:
            msg = ("WARNING: line '%s' found in test "
                   "iteration keyval could not be parsed")
            msg %= line
            tko_utils.dprint(msg)


class status_line(version_0.status_line):
    def __init__(self, indent, status, subdir, testname, reason,
                 optional_fields):
        # handle INFO fields
        if status == "INFO":
            self.type = "INFO"
            self.indent = indent
            self.status = self.subdir = self.testname = self.reason = None
            self.optional_fields = optional_fields
        else:
            # everything else is backwards compatible
            super(status_line, self).__init__(indent, status, subdir,
                                              testname, reason,
                                              optional_fields)


    def is_successful_reboot(self, current_status):
        # make sure this is a reboot line
        if self.testname != "reboot":
            return False

        # make sure this was not a failure
        if status_lib.is_worse_than_or_equal_to(current_status, "FAIL"):
            return False

        # it must have been a successful reboot
        return True


    def get_kernel(self):
        # get the base kernel version
        fields = self.optional_fields
        base = re.sub("-autotest$", "", fields.get("kernel", ""))
        # get a list of patches
        patches = []
        patch_index = 0
        while ("patch%d" % patch_index) in fields:
            patches.append(fields["patch%d" % patch_index])
            patch_index += 1
        # create a new kernel instance
        return kernel(base, patches)


    def get_timestamp(self):
        return tko_utils.get_timestamp(self.optional_fields,
                                       "timestamp")


# the default implementations from version 0 will do for now
patch = version_0.patch


class parser(base.parser):
    @staticmethod
    def make_job(dir):
        return job(dir)


    @staticmethod
    def make_dummy_abort(indent, subdir, testname, timestamp, reason):
        indent = "\t" * indent
        if not subdir:
            subdir = "----"
        if not testname:
            testname = "----"

        # There is no guarantee that this will be set.
        timestamp_field = ''
        if timestamp:
            timestamp_field = '\ttimestamp=%s' % timestamp

        msg = indent + "END ABORT\t%s\t%s%s\t%s"
        return msg % (subdir, testname, timestamp_field, reason)


    @staticmethod
    def put_back_line_and_abort(
        line_buffer, line, indent, subdir, timestamp, reason):
        tko_utils.dprint("Unexpected indent regression, aborting")
        line_buffer.put_back(line)
        abort = parser.make_dummy_abort(
            indent, subdir, subdir, timestamp, reason)
        line_buffer.put_back(abort)


    def state_iterator(self, buffer):
        line = None
        new_tests = []
        job_count, boot_count = 0, 0
        min_stack_size = 0
        stack = status_lib.status_stack()
        current_kernel = kernel("", [])  # UNKNOWN
        current_status = status_lib.statuses[-1]
        current_reason = None
        started_time_stack = [None]
        subdir_stack = [None]
        running_test = None
        running_reasons = set()
        yield []   # we're ready to start running

        # create a RUNNING SERVER_JOB entry to represent the entire test
        running_job = test.parse_partial_test(self.job, "----", "SERVER_JOB",
                                              "", current_kernel,
                                              self.job.started_time)
        new_tests.append(running_job)

        while True:
            # are we finished with parsing?
            if buffer.size() == 0 and self.finished:
                if stack.size() == 0:
                    break
                # we have status lines left on the stack,
                # we need to implicitly abort them first
                tko_utils.dprint('\nUnexpected end of job, aborting')
                abort_subdir_stack = list(subdir_stack)
                if self.job.aborted_by:
                    reason = "Job aborted by %s" % self.job.aborted_by
                    reason += self.job.aborted_on.strftime(
                        " at %b %d %H:%M:%S")
                else:
                    reason = "Job aborted unexpectedly"

                timestamp = line.optional_fields.get('timestamp')
                for i in reversed(xrange(stack.size())):
                    if abort_subdir_stack:
                        subdir = abort_subdir_stack.pop()
                    else:
                        subdir = None
                    abort = self.make_dummy_abort(
                        i, subdir, subdir, timestamp, reason)
                    buffer.put(abort)

            # stop processing once the buffer is empty
            if buffer.size() == 0:
                yield new_tests
                new_tests = []
                continue

            # reinitialize the per-iteration state
            started_time = None
            finished_time = None

            # get the next line
            raw_line = status_lib.clean_raw_line(buffer.get())
            tko_utils.dprint('\nSTATUS: ' + raw_line.strip())
            line = status_line.parse_line(raw_line)
            if line is None:
                tko_utils.dprint('non-status line, ignoring')
                continue

            # do an initial sanity check of the indentation
            expected_indent = stack.size()
            if line.type == "END":
                expected_indent -= 1
            if line.indent < expected_indent:
                # ABORT the current level if indentation was unexpectedly low
                self.put_back_line_and_abort(
                    buffer, raw_line, stack.size() - 1, subdir_stack[-1],
                    line.optional_fields.get("timestamp"), line.reason)
                continue
            elif line.indent > expected_indent:
                # ignore the log if the indent was unexpectedly high
                tko_utils.dprint("unexpected extra indentation, ignoring")
                continue


            # initial line processing
            if line.type == "START":
                stack.start()
                started_time = line.get_timestamp()
                if (line.testname is None and line.subdir is None
                    and not running_test):
                    # we just started a client, all tests are relative to here
                    min_stack_size = stack.size()
                elif stack.size() == min_stack_size + 1 and not running_test:
                    # we just started a new test, insert a running record
                    running_reasons = set()
                    if line.reason:
                        running_reasons.add(line.reason)
                    running_test = test.parse_partial_test(self.job,
                                                           line.subdir,
                                                           line.testname,
                                                           line.reason,
                                                           current_kernel,
                                                           started_time)
                    msg = "RUNNING: %s\nSubdir: %s\nTestname: %s\n%s"
                    msg %= (running_test.status, running_test.subdir,
                            running_test.testname, running_test.reason)
                    tko_utils.dprint(msg)
                    new_tests.append(running_test)
                started_time_stack.append(started_time)
                subdir_stack.append(line.subdir)
                continue
            elif line.type == "INFO":
                # update the current kernel if one is defined in the info
                if "kernel" in line.optional_fields:
                    current_kernel = line.get_kernel()
                continue
            elif line.type == "STATUS":
                # update the stacks
                if line.subdir and stack.size() > min_stack_size:
                    subdir_stack[-1] = line.subdir
                # update the status, start and finished times
                stack.update(line.status)
                if status_lib.is_worse_than_or_equal_to(line.status,
                                                        current_status):
                    if line.reason:
                        # update the status of a currently running test
                        if running_test:
                            running_reasons.add(line.reason)
                            running_reasons = tko_utils.drop_redundant_messages(
                                    running_reasons)
                            sorted_reasons = sorted(running_reasons)
                            running_test.reason = ", ".join(sorted_reasons)
                            current_reason = running_test.reason
                            new_tests.append(running_test)
                            msg = "update RUNNING reason: %s" % line.reason
                            tko_utils.dprint(msg)
                        else:
                            current_reason = line.reason
                    current_status = stack.current_status()
                started_time = None
                finished_time = line.get_timestamp()
                # if this is a non-test entry there's nothing else to do
                if line.testname is None and line.subdir is None:
                    continue
            elif line.type == "END":
                # grab the current subdir off of the subdir stack, or, if this
                # is the end of a job, just pop it off
                if (line.testname is None and line.subdir is None
                    and not running_test):
                    min_stack_size = stack.size() - 1
                    subdir_stack.pop()
                else:
                    line.subdir = subdir_stack.pop()
                    if not subdir_stack[-1] and stack.size() > min_stack_size:
                        subdir_stack[-1] = line.subdir
                # update the status, start and finished times
                stack.update(line.status)
                current_status = stack.end()
                if stack.size() > min_stack_size:
                    stack.update(current_status)
                    current_status = stack.current_status()
                started_time = started_time_stack.pop()
                finished_time = line.get_timestamp()
                # update the current kernel
                if line.is_successful_reboot(current_status):
                    current_kernel = line.get_kernel()
                # adjust the testname if this is a reboot
                if line.testname == "reboot" and line.subdir is None:
                    line.testname = "boot.%d" % boot_count
            else:
                assert False

            # have we just finished a test?
            if stack.size() <= min_stack_size:
                # if there was no testname, just use the subdir
                if line.testname is None:
                    line.testname = line.subdir
                # if there was no testname or subdir, use 'CLIENT_JOB'
                if line.testname is None:
                    line.testname = "CLIENT_JOB.%d" % job_count
                    job_count += 1
                    if not status_lib.is_worse_than_or_equal_to(
                        current_status, "ABORT"):
                        # a job hasn't really failed just because some of the
                        # tests it ran have
                        current_status = "GOOD"

                if not current_reason:
                    current_reason = line.reason
                new_test = test.parse_test(self.job,
                                           line.subdir,
                                           line.testname,
                                           current_status,
                                           current_reason,
                                           current_kernel,
                                           started_time,
                                           finished_time,
                                           running_test)
                running_test = None
                current_status = status_lib.statuses[-1]
                current_reason = None
                if new_test.testname == ("boot.%d" % boot_count):
                    boot_count += 1
                msg = "ADD: %s\nSubdir: %s\nTestname: %s\n%s"
                msg %= (new_test.status, new_test.subdir,
                        new_test.testname, new_test.reason)
                tko_utils.dprint(msg)
                new_tests.append(new_test)

        # the job is finished, produce the final SERVER_JOB entry and exit
        final_job = test.parse_test(self.job, "----", "SERVER_JOB",
                                    self.job.exit_status(), "",
                                    current_kernel,
                                    self.job.started_time,
                                    self.job.finished_time,
                                    running_job)
        new_tests.append(final_job)
        yield new_tests
