import os, sys, re
from autotest_utils import *

class cpuset:
	def available_cpus():
		available = set(range(

	def __init__(self, job_name, job_size, job_pid, cpus):
		# Create a cpuset container and move job_pid into it
		# Allocate the list "cpus" of cpus to that container

		# job name = arbitrary string tag
		# job size = reqested memory for job in bytes
		# job pid = pid of job we're putting into the container

		if not os.path.exists('/dev/cpuset'):
			os.mkdir('/dev/cpuset')
		# if not grep('/dev/cpuset', '/etc/mtab')
			system('mount -t cpuset none /dev/cpuset')

		cmdline = read_one_line('/proc/cmdline')
		fake_numa_nodes = re.search('numa=fake=(\d+)', cmdline).group(1)

		# Bind the specificed cpus to the cpuset
		self.cpudir = "/dev/cpuset/%s" % job_name
		os.mkdir(self.cpudir)
		cpu_spec = ','.join(['%d' % x for x in cpus])
		write_one_line(cpu_spec, '/dev/cpuset/%s/cpus' % job_name)

	  	node_size = memtotal() * 1024 / fake_numa_nodes
		num_nodes = int(math.ceil(job_size / node_size))

		if cpu_number == 0: # First cpuset
			m_start = 3
			m_end = m_start + num_nodes
		else:
			m_end = num_fake_numa_nodes - 1
			m_start = m_end - num_nodes
		alloc_size = (m_end - m_start + 1) * node_size
		mems = os.path.join(self.cpudir, 'mems')
		write_one_line("%d-%d" % (m_start, m_end), self.cpudir + '/mems')
		write_one_line("%d" % job_pid, self.cpudir + 'tasks')
		print "Cpuset: pid %d, cpu %d, memory %s --> nodes %d-%d --> %s" % (job_pid, cpu_number, int2KMG(job_size), m_start, m_end, int2KMG(alloc_size))


	def release(self):
		system("rm -rf %s > /dev/null 2> /dev/null" % self.cpudir)
