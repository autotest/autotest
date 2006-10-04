"""Convenience functions for use by tests or whomever.
"""

import os,os.path,shutil,urllib,sys,signal,commands,pickle
from error import *
import re,string

def grep(pattern, file):
	"""
	This is mainly to fix the return code inversion from grep
	Also handles compressed files. 

	returns 1 if the pattern is present in the file, 0 if not.
	"""
	command = 'grep "%s" > /dev/null' % pattern
	ret = cat_file_to_cmd(file, command, ignorestatus = 1)
	return not ret
	
	
def difflist(list1, list2):
	"""returns items in list2 that are not in list1"""
	diff = [];
	for x in list2:
		if x not in list1:
			diff.append(x)
	return diff


def cat_file_to_cmd(file, command, ignorestatus = 0):
	"""
	equivalent to 'cat file | command' but knows to use 
	zcat or bzcat if appropriate
	"""
	if not os.path.isfile(file):
		raise NameError, 'invalid file %s to cat to command %s' % file, command
	if file.endswith('.bz2'):
		return system('bzcat ' + file + ' | ' + command, ignorestatus)
	elif (file.endswith('.gz') or file.endswith('.tgz')):
		return system('zcat ' + file + ' | ' + command, ignorestatus)
	else:
		return system('cat ' + file + ' | ' + command, ignorestatus)


def extract_tarball_to_dir(tarball, dir):
	"""
	Extract a tarball to a specified directory name instead of whatever 
	the top level of a tarball is - useful for versioned directory names, etc
	"""
	if os.path.exists(dir):
		raise NameError, 'target %s already exists' % dir
	pwd = os.getcwd()
	os.chdir(os.path.dirname(os.path.abspath(dir)))
	newdir = extract_tarball(tarball)
	os.rename(newdir, dir)
	os.chdir(pwd)


def extract_tarball(tarball):
	"""Returns the first found newly created directory by the tarball extraction"""
	oldlist = os.listdir('.')
	cat_file_to_cmd(tarball, 'tar xf -')
	newlist = os.listdir('.')
	newfiles = difflist(oldlist, newlist)   # what is new dir ?
	new_dir = None
	for newfile in newfiles:
		if (os.path.isdir(newfile)):
			return newfile
	raise NameError, "extracting tarball produced no dir"


def update_version(srcdir, new_version, install, *args, **dargs):
	"""Make sure srcdir is version new_version

	If not, delete it and install() the new version
	"""
	versionfile = srcdir + '/.version'
	if os.path.exists(srcdir):
		if os.path.exists(versionfile):
			old_version = pickle.load(open(versionfile, 'r'))
			if (old_version != new_version):
				system('rm -rf ' + srcdir)
		else:
			system('rm -rf ' + srcdir)
	if not os.path.exists(srcdir):
		install(*args, **dargs)
		if os.path.exists(srcdir):
			pickle.dump(new_version, open(versionfile, 'w'))
                

def is_url(path):
	"""true if path is a url
	"""
	# should cope with other url types here, but we only handle http and ftp
	if (path.startswith('http://')) or (path.startswith('ftp://')):
		return 1
	return 0


def get_file(src, dest):
	"""get a file, either from url or local"""
	if (src == dest):      # no-op here allows clean overrides in tests
		return
	if (is_url(src)):
		print 'PWD: ' + os.getcwd()
		print 'Fetching \n\t', src, '\n\t->', dest
		try:
			urllib.urlretrieve(src, dest)
		except IOError:
			sys.stderr.write("Unable to retrieve %s (to %s)\n" % (src, dest))
			sys.exit(1)
		return dest
	shutil.copyfile(src, dest)
	return dest


def unmap_url(srcdir, src, destdir = '.'):
	"""
	Receives either a path to a local file or a URL.
	returns either the path to the local file, or the fetched URL

	unmap_url('/usr/src', 'foo.tar', '/tmp')
				= '/usr/src/foo.tar'
	unmap_url('/usr/src', 'http://site/file', '/tmp')
				= '/tmp/file'
				(after retrieving it)
	"""
	if is_url(src):
		dest = destdir + '/' + os.path.basename(src)
		get_file(src, dest)
		return dest
	else:
		return srcdir + '/' + src


def basename(path):
	i = path.rfind('/');
	return path[i+1:]


def force_copy(src, dest):
	"""Replace dest with a new copy of src, even if it exists"""
	if os.path.isfile(dest):
		os.remove(dest)
	return shutil.copyfile(src, dest)


def force_link(src, dest):
	"""Link src to dest, overwriting it if it exists"""
	return system("ln -sf %s %s" % (src, dest))


def file_contains_pattern(file, pattern):
	"""Return true if file contains the specified egrep pattern"""
	if not os.path.isfile(file):
		raise NameError, 'file %s does not exist' % file
	return not system('egrep -q "' + pattern + '" ' + file, ignorestatus = 1)


def list_grep(list, pattern):
	"""True if any item in list matches the specified pattern."""
	compiled = re.compile(pattern)
	for line in list:
		match = compiled.search(line)
		if (match):
			return 1
	return 0

def get_os_vendor():
	"""Try to guess what's the os vendor
	"""
	issue = '/etc/issue'
	
	if not os.path.isfile(issue):
		return 'Unknown'
	
	if file_contains_pattern(issue, 'Red Hat'):
		return 'Red Hat'
	elif file_contains_pattern(issue, 'Fedora Core'):
		return 'Fedora Core'
	elif file_contains_pattern(issue, 'SUSE'):
		return 'SUSE'
	elif file_contains_pattern(issue, 'Ubuntu'):
		return 'Ubuntu'
	else:
		return 'Unknown'
	

def get_vmlinux():
	"""Return the full path to vmlinux

	Ahem. This is crap. Pray harder. Bad Martin.
	"""
	vmlinux = '/boot/vmlinux-%s' % system_output('uname -r')
	if os.path.isfile(vmlinux):
		return vmlinux
	return None


def get_systemmap():
	"""Return the full path to System.map

	Ahem. This is crap. Pray harder. Bad Martin.
	"""
	map = '/boot/System.map-%s' % system_output('uname -r')
	if os.path.isfile(map):
		return map
	return None


def get_modules_dir():
	"""Return the modules dir for the running kernel version"""
	kernel_version = system_output('uname -r')
	return '/lib/modules/%s/kernel' % kernel_version


def get_cpu_arch():
	"""Work out which CPU architecture we're running on"""
	f = open('/proc/cpuinfo', 'r')
	cpuinfo = f.readlines()
	f.close()
	if list_grep(cpuinfo, '^cpu.*(RS64|POWER3|Broadband Engine)'):
		return 'power'
	elif list_grep(cpuinfo, '^cpu.*POWER4'):
		return 'power4'
	elif list_grep(cpuinfo, '^cpu.*POWER5'):
		return 'power5'
	elif list_grep(cpuinfo, '^cpu.*POWER6'):
		return 'power6'
	elif list_grep(cpuinfo, '^cpu.*PPC970'):
		return 'power970'
	elif list_grep(cpuinfo, 'Opteron'):
		return 'x86_64'
	elif list_grep(cpuinfo, 'GenuineIntel') and list_grep(cpuinfo, '48 bits virtual'):
		return 'x86_64'
	else:
		return 'i386'


def get_kernel_arch():
	"""Work out the current kernel architecture (as a kernel arch)"""
	arch = os.popen('uname -m').read().rstrip()
	if ((arch == 'i586') or (arch == 'i686')):
		return 'i386'
	else:
		return arch


def get_file_arch(filename):
	# -L means follow symlinks
	file_data = system_output('file -L ' + filename)
	if file_data.count('80386'):
		return 'i386'
	return None


def kernelexpand(kernel):
	# if not (kernel.startswith('http://') or kernel.startswith('ftp://') or os.path.isfile(kernel)):
	if kernel.find('/') < 0:     # contains no path.
		autodir = os.environ['AUTODIR']
		kernelexpand = os.path.join(autodir, 'tools/kernelexpand')
		w, r = os.popen2(kernelexpand + ' ' + kernel)

		kernel = r.readline().strip()
		r.close()
		w.close()
	return kernel.split()


def count_cpus():
	"""number of CPUs in the local machine according to /proc/cpuinfo"""
	f = file('/proc/cpuinfo', 'r')
	cpus = 0
	for line in f.readlines():
		if line.startswith('processor'):
			cpus += 1
	return cpus

def system(cmd, ignorestatus = 0):
	"""os.system replacement

	We have our own definition of system here, as the stock os.system doesn't
	correctly handle sigpipe 
	(ie things like "yes | head" will hang because yes doesn't get the SIGPIPE).
 
	Also the stock os.system didn't raise errors based on exit status, this 
	version does unless you explicitly specify ignorestatus=1
	"""
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
	try:
		status = os.system(cmd)
	finally:
		signal.signal(signal.SIGPIPE, signal.SIG_IGN)

	if ((status != 0) and not ignorestatus):
		raise CmdError(cmd, status)
	return status


def system_output(command, ignorestatus = 0):
	"""Run command and return its output

	ignorestatus
		whether to raise a CmdError if command has a nonzero exit status
	"""
	(result, data) = commands.getstatusoutput(command)
	if ((result != 0) and not ignorestatus):
		raise CmdError, 'command failed: ' + command
	return data


def where_art_thy_filehandles():
	"""Dump the current list of filehandles"""
	os.system("ls -l /proc/%d/fd >> /dev/tty" % os.getpid())


def print_to_tty(string):
	"""Output string straight to the tty"""
	os.system("echo " + string + " >> /dev/tty")


def dump_object(object):
	"""Dump an object's attributes and methods

	kind of like dir()
	"""
	for item in object.__dict__.iteritems():
		print item
		try:
			(key,value) = item
			dump_object(value)
		except:
			continue


def environ(env_key):
	"""return the requested environment variable, or '' if unset"""
	if (os.environ.has_key(env_key)):
		return os.environ[env_key]
	else:
		return ''


def prepend_path(newpath, oldpath):
	"""prepend newpath to oldpath"""
	if (oldpath):
		return newpath + ':' + oldpath
	else:
		return newpath


def append_path(oldpath, newpath):
	"""append newpath to oldpath"""
	if (oldpath):
		return oldpath + ':' + newpath
	else:
		return newpath


def avgtime_print(dir):
	""" Calculate some benchmarking statistics.
	    Input is a directory containing a file called 'time'.
	    File contains one-per-line results of /usr/bin/time.
	    Output is average Elapsed, User, and System time in seconds,
	      and average CPU percentage.
	"""
	f = open(dir + "/time")
	user = system = elapsed = cpu = count = 0
	r = re.compile('([\d\.]*)user ([\d\.]*)system (\d*):([\d\.]*)elapsed (\d*)%CPU')
	for line in f.readlines():
		try:
			s = r.match(line);
			user += float(s.group(1))
			system += float(s.group(2))
			elapsed += (float(s.group(3)) * 60) + float(s.group(4))
			cpu += float(s.group(5))
			count += 1
		except:
			raise ValueError("badly formatted times")
			
	f.close()
	return "Elapsed: %0.2fs User: %0.2fs System: %0.2fs CPU: %0.0f%%" % \
	      (elapsed/count, user/count, system/count, cpu/count)


def running_config():
	"""
	Return path of config file of the currently running kernel
	"""
	for config in ('/proc/config.gz', \
		       '/boot/config-%s' % system_output('uname -r') ):
		if os.path.isfile(config):
			return config
	return None
