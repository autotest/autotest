__author__ = """Copyright Google, Peter Dahl, Martin J. Bligh   2007"""

import os, sys, re, glob, math
from autotest_utils import *

# Convert '1-3,7,9-12' to [1,2,3,7,9,10,11,12]
def rangelist_to_list(rangelist):
	result = []
	if not rangelist:
		return result
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
		raise "Cannot understand data input: %s %s" % (x, rangelist)
	return result

class cpuset:
	def print_one_cpuset(self, name):
		dir = os.path.join('/dev/cpuset', name)
		print "%s:" % name
		print "\tcpus: %s" % read_one_line(dir + '/cpus')
		mems = read_one_line(dir + '/mems')
		print "\tmems: %s" % mems
		memtotal = node_size() * len(rangelist_to_list(mems))
		print "\tmemtotal: %s" % human_format(memtotal)
		tasks = [x.rstrip() for x in open(dir + '/tasks').readlines()]
		print "\ttasks: %s" % ','.join(tasks)

	def print_all_cpusets():
		for cpuset in glob.glob('/dev/cpuset/*'):
			print_one_cpuset(re.sub(r'.*/', '', cpuset))


	def display(self):
		self.print_one_cpuset(os.path.join(self.root,self.name))

	def get_mems(self, root):
		file_name = "%s/mems" % root
		if os.path.exists(file_name):
			return read_one_line(file_name)
		else:
			return ""

	# Start with the nodes available one level up in the cpuset tree,
	# substract off all siblings at this level that are not self.cpudir.
	def available_mems(self):
	#	print "self_root:", self.root
		root_mems = self.get_mems(self.root)
	#	print "root_mems:", root_mems
		available = rangelist_to_list(root_mems) # how much is available in root

	#	print "available:", available
		for sub_cpusets in glob.glob('%s/*/mems' % self.root):
			sub_cpusets = os.path.dirname(sub_cpusets)
			mems = self.get_mems(sub_cpusets)
			if mems:
				tmp = rangelist_to_list(mems)
				available = filter( lambda x: x not in tmp, available ) # available - tmp
	#	print "final available", available
		return available

	def release(self):
		print "erasing ", self.cpudir
		return
		if self.delete_after_use:
			system("for i in `cat %s/tasks`; do kill -9 $i; done;sleep 3; rmdir %s" % (self.cpudir, self.cpudir))

	def __init__(self, name, job_size, job_pid, cpus = None,
	    root = "", cleanup = 1):
		# Create a cpuset container and move job_pid into it
		# Allocate the list "cpus" of cpus to that container

		# name = arbitrary string tag
		# job size = reqested memory for job in bytes
		# job pid = pid of job we're putting into the container
		self.super_root = "/dev/cpuset"
		self.root = os.path.join(self.super_root, root)
		self.name = name
		self.delete_after_use = 1
		if not grep('cpuset', '/proc/filesystems'):
			print "No CPU set support"
			return
		if not os.path.exists(self.super_root):
			os.mkdir(self.super_root)
			system('mount -t cpuset none %s' % self.super_root)
		if cpus == None:
			cpus = range(0, count_cpus())
		print "cpus=", cpus
		all_nodes = numa_nodes()

		print "all_nodes=", all_nodes
		# Bind the specificed cpus to the cpuset
		self.cpudir = os.path.join(self.root, name)
		if not os.path.exists(self.cpudir):
			self.delete_after_use = 1
			os.mkdir(self.cpudir)
			cpu_spec = ','.join(['%d' % x for x in cpus])

			# Find some free nodes to use to create this 
			# cpuset
			node_size = memtotal() * 1024 / len(all_nodes)
			nodes_needed = int(math.ceil(job_size / node_size))

			mems = self.available_mems()[-nodes_needed:]
			alloc_size = human_format(len(mems) * node_size)
			if len(mems) < nodes_needed:
				raise "Insufficient memory available"

		# Set up the cpuset
			mems_spec = ','.join(['%d' % x for x in mems])
			print "cpu_spec", mems_spec
			print "mems_spec", mems_spec
			print "self.cpudir=", self.cpudir
			print "wrote %s to %s/cpus" % (cpu_spec, self.cpudir)
			write_one_line(os.path.join(self.cpudir, 'cpus'), cpu_spec)
			write_one_line(os.path.join(self.cpudir, 'mems'), mems_spec)
			write_one_line(os.path.join(self.cpudir, 'tasks'), "%d" % job_pid)
			# Notify kernel to erase the container after it  is done.
			if cleanup:
			 	write_one_line(
				    os.path.join(self.cpudir, 
				    'notify_on_release'), "1")
 

			print "Created cpuset for pid %d, size %s" % \
				(job_pid, human_format(job_size))
		else:
			# CPU set exists; Just add the pid to it.
			write_one_line("%s" % job_pid,
			    os.path.join(self.cpudir, 'tasks'))

		self.display()
		return

