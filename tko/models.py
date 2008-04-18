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


class patch(object):
	def __init__(self, spec, reference, hash):
		self.spec = spec
		self.reference = reference
		self.hash = hash


class iteration(object):
	def __init__(self, index, keyval):
		self.index = index
		self.keyval = keyval
