import os, md5

from autotest_lib.client.common_lib import utils
from autotest_lib.tko import utils as tko_utils


class job(object):
	def __init__(self, dir, user, label, machine, queued_time,
		     started_time, finished_time, machine_owner):
		self.dir = dir
		self.tests = []
		self.user = user
		self.label = label
		self.machine = machine
		self.queued_time = queued_time
		self.started_time = started_time
		self.finished_time = finished_time
		self.machine_owner = machine_owner


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
		     attributes):
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


	@staticmethod
	def load_iterations(keyval_path):
		"""Abstract method to load a list of iterations from a keyval
		file."""
		raise NotImplemented


	@classmethod
	def parse_test(cls, job, subdir, testname, status, reason, test_kernel,
		       started_time, finished_time):
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
			iterations = iteration.load_from_keyval(
			    iteration_keyval)

			# grab test attributes from the subdir keyval
			test_keyval = os.path.join(job.dir, subdir, "keyval")
			attributes = test.load_attributes(test_keyval)
		else:
			iterations = []
			attributes = {}

		return cls(subdir, testname, status, reason, test_kernel,
			   job.machine, started_time, finished_time,
			   iterations, attributes)


	@staticmethod
	def load_attributes(keyval_path):
		"""Load the test attributes into a dictionary from a test
		keyval path. Does not assume that the path actually exists."""
		if not os.path.exists(keyval_path):
			return {}
		return utils.read_keyval(keyval_path)


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
		raise NotImplemented


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
		for line in file(path):
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
