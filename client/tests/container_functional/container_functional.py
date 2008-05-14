import os

from autotest_lib.client.bin import cpuset
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import utils


class container_functional(test.test):
	version = 1

	def execute(self, mbytes=None, cpus=None, root='', name=None):
		"""Check that the container was setup.
		The arguments must be the same than
		job.new_container()"""
		if not name:
			raise error.TestError("Must have a container name")

		# Do container exists?
		for container in ['sys', name]:
			try:
				utils.system('ls %s > /dev/null' % \
					     os.path.join('/dev/cpuset',
							  container))
			except error.CmdError:
				raise error.TestError("Container %s not created." % \
						      container)

		# Did we get the CPUs?
		if cpus:
			actual_cpus = utils.system_output('cat %s' % \
							  os.path.join('/dev/cpuset',
								       name,
								       'cpus'))
			if cpus != cpuset.rangelist_to_list(actual_cpus):
				raise error.TestError(("CPUs = %s, "
						      "expecting: %s") %
						      (actual_cpus, cpus))

		# Are we in this container?
		actual_pid = utils.system_output('cat %s' % \
						 os.path.join('/dev/cpuset',
							      name,
							      'tasks'))

 		if str(os.getpid()) not in actual_pid:
 			raise error.TestError("My pid %s is not in "
 					      "container task list: %s" % \
 					      (str(os.getpid()), actual_pid))

		# Our memory nodes != sys memory nodes
		actual_mems = utils.system_output('cat %s' % \
						  os.path.join('/dev/cpuset',
							       name,
							       'mems'))
		sys_mems = utils.system_output('cat %s' % \
					       os.path.join('/dev/cpuset',
							    'sys',
							    'mems'))

		actual_nodes = set(cpuset.rangelist_to_list(actual_mems))
		sys_nodes = set(cpuset.rangelist_to_list(sys_mems))

		if actual_nodes.intersection(sys_nodes):
			raise error.TestError("Sys nodes = %s\n"
					      "My nodes = %s" % \
					      (sys_nodes, actual_nodes))

		# Should only have one node for 100MB
		if len(actual_nodes) != 1:
			raise error.TestError(("Got more than 1 node: %s" %
					       actual_nodes))
