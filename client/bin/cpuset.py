import os, sys

class cpuset:
	def __init__(self, job_name, memory_size, numa_fake, job_size, job_pid, cpu_number):
		if not os.path.exists('/dev/cpuset'):
			os.mkdir('/dev/cpuset')
		# if not grep('/dev/cpuset', '/etc/mtab')
			system('mount -t cpuset none /dev/cpuset')

	self.cpudir = "/dev/cpuset/%s" % job_name
	os.mkdir(self.cpudir)
	write_one_line("%d" % cpu_number, '/dev/cpuset/%s/cpus' % job_name)
  	node_size = memory_size / numa_fake
	num_nodes = int(math.ceil(job_size / node_size))
	if cpu_number == 0:
		m_start = 3
		m_end = m_start + num_nodes
	else:
		m_end = numa_fake - 1
		m_start = m_end - num_nodes
	alloc_size = (m_end - m_start + 1) * node_size
	mems = os.path.join(self.cpudir, 'mems')
	write_one_line("%d-%d" % (m_start, m_end), self.cpudir + '/mems')
	write_one_line("%d" % job_pid, self.cpudir + 'tasks')
	print "Cpuset: pid %d, cpu %d, memory %s --> nodes %d-%d --> %s" % (job_pid, cpu_number, int2KMG(job_size), m_start, m_end, int2KMG(alloc_size))


	def release(self):
		system("rm -rf %s > /dev/null 2> /dev/null" % self.cpudir)
