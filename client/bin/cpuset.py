__author__ = """Copyright Google, Peter Dahl, Martin J. Bligh   2007"""

import os, sys, re, glob
from autotest_utils import *

class cpuset:
	# Convert '1-3,7,9-12' to [1,2,3,7,9,10,11,12]
	def rangelist_to_list(rangelist):
		result = []
		for x in rangelist.split(','):
			if re.match(r'^(\d+)$', x):
				result.append(int(x))
				continue
			m = re.match(r'^(\d+)-(\d+)$', x)
			if m:
				start = int(m.group(1))
				end = int(m.group(2))
				result += range(start, end+1)
				continue
			raise 'Cannot understand data input %s' % x
		return result


	def available_nems(all_mems):
		available = set(all_mems)
		for mems in glob.glob('/dev/cpuset/*/mems'):
			available -= set(rangelist_to_list(read_one_line(mems)))
		return available


	def print_one_cpuset(name):
		dir = os.path.join('/dev/cpuset', name)
		print "%s:" % name
		print "\tcpus: %s" % read_one_line(dir + '/cpus')
		mems = read_one_line(dir + '/mems')
		print "\tmems: %s" % mems
		memtotal = node_size() * len(rangelist_to_list(mems))
		print "\tmemtotal: %s" % human_format(memtotal)
		tasks = [x.rstrip() for x in open(dir + '/tasks').readlines()])
		print "\ttasks: %s" % ','.join(tasks)


	def print_all_cpusets():
		for cpuset in glob.glob('/dev/cpuset/*'):
			print_one_cpuset(re.sub(r'.*/', '', cpuset)


	def __init__(self, name, job_size, job_pid, cpus):
		# Create a cpuset container and move job_pid into it
		# Allocate the list "cpus" of cpus to that container

		# name = arbitrary string tag
		# job size = reqested memory for job in bytes
		# job pid = pid of job we're putting into the container

		if not os.path.exists('/dev/cpuset'):
			os.mkdir('/dev/cpuset')
		# if not grep('/dev/cpuset', '/etc/mtab')
			system('mount -t cpuset none /dev/cpuset')

		cmdline = read_one_line('/proc/cmdline')
		all_nodes = numa_nodes()

		# Bind the specificed cpus to the cpuset
		self.cpudir = "/dev/cpuset/%s" % name
		os.mkdir(self.cpudir)
		cpu_spec = ','.join(['%d' % x for x in cpus])
		write_one_line(cpu_spec, '/dev/cpuset/%s/cpus' % name)

		# Find some free nodes to use to create this cpuset
	  	node_size = memtotal() * 1024 / len(all_nodes)
		nodes_needed = int(math.ceil(job_size / node_size))
		mems = available_mems(all_nodes)[-nodes_needed:]
		alloc_size = human_format(len(mems) * node_size)
		if len(mems) < nodes_needed:
			raise "Insufficient memory available"

		# Set up the cpuset
		mems_spec = ','.join(['%d' % x for x in mems])
		write_one_line(mems_spec, os.path.join(self.cpudir, 'mems'))
		write_one_line('%d'%job_pid, os.path.join(self.cpudir, 'tasks'))

		print "Created cpuset for pid %d, size %s" % \
					(job_pid, human_format(job_size))
		self.print()


	def print(self):
		print_one_cpuset(self.name)


	def release(self):
		system("rm -rf %s > /dev/null 2> /dev/null" % self.cpudir)
