import os, md5

from autotest_lib.client.common_lib import utils
from autotest_lib.tko import utils as tko_utils


class job(object):
    def __init__(self, dir, user, label, machine, queued_time, started_time,
                 finished_time, machine_owner, machine_group, aborted_by,
                 aborted_on):
        self.dir = dir
        self.tests = []
        self.user = user
        self.label = label
        self.machine = machine
        self.queued_time = queued_time
        self.started_time = started_time
        self.finished_time = finished_time
        self.machine_owner = machine_owner
        self.machine_group = machine_group
        self.aborted_by = aborted_by
        self.aborted_on = aborted_on


    @staticmethod
    def read_keyval(dir):
        dir = os.path.normpath(dir)
        top_dir = tko_utils.find_toplevel_job_dir(dir)
        if not top_dir:
            top_dir = dir
        assert(dir.startswith(top_dir))

        # pull in and merge all the keyval files, with higher-level
        # overriding values in the lower-level ones
        keyval = {}
        while True:
            try:
                upper_keyval = utils.read_keyval(dir)
                # HACK: exclude hostname from the override - this is a special
                # case where we want lower to override higher
                if "hostname" in upper_keyval and "hostname" in keyval:
                    del upper_keyval["hostname"]
                keyval.update(upper_keyval)
            except IOError:
                pass  # if the keyval can't be read just move on to the next
            if dir == top_dir:
                break
            else:
                assert(dir != "/")
                dir = os.path.dirname(dir)
        return keyval



class kernel(object):
    def __init__(self, base, patches, kernel_hash):
        self.base = base
        self.patches = patches
        self.kernel_hash = kernel_hash


    @staticmethod
    def compute_hash(base, hashes):
        key_string = ','.join([base] + hashes)
        return md5.new(key_string).hexdigest()


class test(object):
    def __init__(self, subdir, testname, status, reason, test_kernel,
                 machine, started_time, finished_time, iterations,
                 attributes, labels):
        self.subdir = subdir
        self.testname = testname
        self.status = status
        self.reason = reason
        self.kernel = test_kernel
        self.machine = machine
        self.started_time = started_time
        self.finished_time = finished_time
        self.iterations = iterations
        self.attributes = attributes
        self.labels = labels


    @staticmethod
    def load_iterations(keyval_path):
        """Abstract method to load a list of iterations from a keyval
        file."""
        raise NotImplementedError


    @classmethod
    def parse_test(cls, job, subdir, testname, status, reason, test_kernel,
                   started_time, finished_time, existing_instance=None):
        """Given a job and the basic metadata about the test that
        can be extracted from the status logs, parse the test
        keyval files and use it to construct a complete test
        instance."""
        tko_utils.dprint("parsing test %s %s" % (subdir, testname))

        if subdir:
            # grab iterations from the results keyval
            iteration_keyval = os.path.join(job.dir, subdir,
                                            "results", "keyval")
            iterations = cls.load_iterations(iteration_keyval)

            # grab test attributes from the subdir keyval
            test_keyval = os.path.join(job.dir, subdir, "keyval")
            attributes = test.load_attributes(test_keyval)
        else:
            iterations = []
            attributes = {}

        # grab test+host attributes from the host keyval
        host_keyval = cls.parse_host_keyval(job.dir, job.machine)
        attributes.update(dict(("host-%s" % k, v)
                               for k, v in host_keyval.iteritems()))

        if existing_instance:
            def constructor(*args, **dargs):
                existing_instance.__init__(*args, **dargs)
                return existing_instance
        else:
            constructor = cls
        return constructor(subdir, testname, status, reason, test_kernel,
                           job.machine, started_time, finished_time,
                           iterations, attributes, [])


    @classmethod
    def parse_partial_test(cls, job, subdir, testname, reason, test_kernel,
                           started_time):
        """Given a job and the basic metadata available when a test is
        started, create a test instance representing the partial result.
        Assume that since the test is not complete there are no results files
        actually available for parsing."""
        tko_utils.dprint("parsing partial test %s %s" % (subdir, testname))

        return cls(subdir, testname, "RUNNING", reason, test_kernel,
                   job.machine, started_time, None, [], {}, [])


    @staticmethod
    def load_attributes(keyval_path):
        """Load the test attributes into a dictionary from a test
        keyval path. Does not assume that the path actually exists."""
        if not os.path.exists(keyval_path):
            return {}
        return utils.read_keyval(keyval_path)


    @staticmethod
    def parse_host_keyval(job_dir, hostname):
        # the "real" job dir may be higher up in the directory tree
        job_dir = tko_utils.find_toplevel_job_dir(job_dir)
        if not job_dir:
            return {} # we can't find a top-level job dir with host keyvals

        # the keyval is <job_dir>/host_keyvals/<hostname> if it exists
        keyval_path = os.path.join(job_dir, "host_keyvals", hostname)
        if os.path.isfile(keyval_path):
            return utils.read_keyval(keyval_path)
        else:
            return {}


class patch(object):
    def __init__(self, spec, reference, hash):
        self.spec = spec
        self.reference = reference
        self.hash = hash


class iteration(object):
    def __init__(self, index, attr_keyval, perf_keyval):
        self.index = index
        self.attr_keyval = attr_keyval
        self.perf_keyval = perf_keyval



    @staticmethod
    def parse_line_into_dicts(line, attr_dict, perf_dict):
        """Abstract method to parse a keyval line and insert it into
        the appropriate dictionary.
                attr_dict: generic iteration attributes
                perf_dict: iteration performance results
        """
        raise NotImplementedError


    @classmethod
    def load_from_keyval(cls, keyval_path):
        """Load a list of iterations from an iteration keyval file.
        Keyval data from separate iterations is separated by blank
        lines. Makes use of the parse_line_into_dicts method to
        actually parse the individual lines."""
        if not os.path.exists(keyval_path):
            return []

        iterations = []
        index = 1
        attr, perf = {}, {}
        for line in file(keyval_path):
            line = line.strip()
            if line:
                cls.parse_line_into_dicts(line, attr, perf)
            else:
                iterations.append(cls(index, attr, perf))
                index += 1
                attr, perf = {}, {}
        if attr or perf:
            iterations.append(cls(index, attr, perf))
        return iterations
