import os,os.path,shutil,urllib,sys,signal,commands,pickle
from error import *
import re

def grep(pattern, file):
# This is mainly to fix the return code inversion from grep
	return not system('grep "' + pattern + '" "' + file + '"')
	
	
def difflist(list1, list2):	
# returns items in list 2 that are not in list 1
	diff = [];
	for x in list2:
		if x not in list1:
			diff.append(x)
	return diff

def cat_file_to_cmd(file, command):
	if not os.path.isfile(file):
		raise NameError, 'invalid file %s to cat to command %s' % file, command
	if file.endswith('.bz2'):
		system('bzcat ' + file + ' | ' + command)
	elif (file.endswith('.gz') or file.endswith('.tgz')):
		system('zcat ' + file + ' | ' + command)
	else:
		system('cat ' + file + ' | ' + command)

	
# Extract a tarball to a specified directory name instead of whatever 
# the top level of a tarball is - useful for versioned directory names, etc
def extract_tarball_to_dir(tarball, dir):
	if os.path.exists(dir):
		raise NameError, 'target %s already exists' % dir
	pwd = os.getcwd()
	os.chdir(os.path.dirname(os.path.abspath(dir)))
	newdir = extract_tarball(tarball)
	os.rename(newdir, dir)
	os.chdir(pwd)


# Returns the first found newly created directory by the tarball extraction
def extract_tarball(tarball):
	oldlist = os.listdir('.')
	cat_file_to_cmd(tarball, 'tar xf -')
	newlist = os.listdir('.')
	newfiles = difflist(oldlist, newlist)   # what is new dir ?
	new_dir = None
	for newfile in newfiles:
		if (os.path.isdir(newfile)):
			return newfile
	raise NameError, "extracting tarball produced no dir"


def update_version(srcdir, new_version, install):
	versionfile = srcdir + '/.version'
	if os.path.exists(srcdir):
		if os.path.exists(versionfile):
			old_version = pickle.load(open(versionfile, 'r'))
			if (old_version != new_version):
				system('rm -rf ' + srcdir)
		else:
			system('rm -rf ' + srcdir)
	if not os.path.exists(srcdir):
		install()
		if os.path.exists(srcdir):
			pickle.dump(new_version, open(versionfile, 'w'))
                

def is_url(path):
	if (path.startswith('http://')) or (path.startswith('ftp://')):
	# should cope with other url types here, but we don't handle them yet
		return 1
	return 0


def get_file(src, dest):
	if (src == dest):      # no-op here allows clean overrides in tests
		return
	# get a file, either from url or local
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
	if os.path.isfile(dest):
		os.remove(dest)
	return shutil.copyfile(src, dest)


def file_contains_pattern(file, pattern):
	if not os.path.isfile(file):
		raise NameError, 'file %s does not exist' % file
	return not system('egrep -q ' + pattern + ' ' + file, ignorestatus = 1)


def list_grep(list, pattern):
	compiled = re.compile(pattern)
	for line in list:
		match = compiled.search(line)
		if (match):
			return 1
	return 0


def get_vmlinux():
	# Ahem. This is crap. Pray harder. Bad Martin.
	vmlinux = '/boot/vmlinux'
	if not os.path.isfile(vmlinux):
		raise NameError, 'Cannot find vmlinux'
	return vmlinux


def get_systemmap():
	# Ahem. This is crap. Pray harder. Bad Martin.
	map = '/boot/System.map'
	if not os.path.isfile(map):
		raise NameError, 'Cannot find System.map'
	return map


def get_modules_dir():
	kernel_version = system_output('uname -r')
	return '/lib/modules/%s/kernel' % kernel_version


def get_arch():
# Work out which CPU architecture we're running on
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


def get_target_arch():
	arch = get_arch()
	if arch.startswith('power'):
		return 'ppc64'
	else:
		return arch


def kernelexpand(kernel):
	# if not (kernel.startswith('http://') or kernel.startswith('ftp://') or os.path.isfile(kernel)):
	if kernel.find('/'):
		w, r = os.popen2('./kernelexpand ' + kernel)

		kernel = r.readline().strip()
		r.close()
		w.close()
	return kernel


def count_cpus():
	f = file('/proc/cpuinfo', 'r')
	cpus = 0
	for line in f.readlines():
		if line.startswith('processor'):
			cpus += 1
	return cpus


# We have our own definition of system here, as the stock os.system doesn't
# correctly handle sigpipe 
# (ie things like "yes | head" will hang because yes doesn't get the SIGPIPE).
# 
# Also the stock os.system didn't raise errors based on exit status, this 
# version does unless you explicitly specify ignorestatus=1
def system(cmd, ignorestatus = 0):
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
	try:
		status = os.system(cmd)
	finally:
		signal.signal(signal.SIGPIPE, signal.SIG_IGN)

	if ((status != 0) and not ignorestatus):
		raise CmdError(cmd, status)
	return status


def system_output(command, ignorestatus = 0):
	(result, data) = commands.getstatusoutput(command)
	if ((result != 0) and not ignorestatus):
		raise CmdError, 'command failed: ' + command
	return data


def where_art_thy_filehandles():
	os.system("ls -l /proc/%d/fd >> /dev/tty" % os.getpid())


def print_to_tty(string):
	os.system("echo " + string + " >> /dev/tty")


def dump_object(object):
	for item in object.__dict__.iteritems():
		print item
		try:
			(key,value) = item
			dump_object(value)
		except:
			continue


def environ(env_key):
	if (os.environ.has_key(env_key)):
		return os.environ(env_key)
	else:
		return ''


def prepend_path(newpath, oldpath):
	if (oldpath):
		return newpath + ':' + oldpath
	else:
		return newpath


def append_path(oldpath, newpath):
	if (oldpath):
		return oldpath + ':' + newpath
	else:
		return newpath


class fd_stack:
	# Note that we need to redirect both the sys.stdout type descriptor
	# (which print, etc use) and the low level OS numbered descriptor
	# which os.system() etc use.

	def __init__(self, fd, filehandle):
		self.fd = fd				# eg 1
		self.filehandle = filehandle		# eg sys.stdout
		self.stack = [(fd, filehandle)]


	def redirect(self, filename):
		fdcopy = os.dup(self.fd)
		self.stack.append( (fdcopy, self.filehandle) )
		# self.filehandle = file(filename, 'w')
		if (os.path.isfile(filename)):
			newfd = os.open(filename, os.O_WRONLY)
		else:
			newfd = os.open(filename, os.O_WRONLY | os.O_CREAT)
		os.dup2(newfd, self.fd)
		os.close(newfd)
		self.filehandle = os.fdopen(self.fd, 'w')


	def tee_redirect(self, filename):
		print_to_tty("tee_redirect to " + filename)
		where_art_thy_filehandles()
		fdcopy = os.dup(self.fd)
		self.stack.append( (fdcopy, self.filehandle) )
		r, w = os.pipe()
		pid = os.fork()
		if pid:			# parent
			os.close(r)
			os.dup2(w, self.fd)
			os.close(w)
		else:			# child
			os.close(w)
			os.dup2(r, 0)
			os.dup2(2, 1)
			os.execlp('tee', 'tee', filename)
		self.filehandle = os.fdopen(self.fd, 'w')
		where_art_thy_filehandles()
		print_to_tty("done tee_redirect to " + filename)

	
	def restore(self):
		# print_to_tty("ENTERING RESTORE %d" % self.fd)
		# where_art_thy_filehandles()
		(old_fd, old_filehandle) = self.stack.pop()
		# print_to_tty("old_fd %d" % old_fd)
		# print_to_tty("self.fd %d" % self.fd)
		self.filehandle.close()   # seems to close old_fd as well.
		# where_art_thy_filehandles()
		os.dup2(old_fd, self.fd)
		# print_to_tty("CLOSING FD %d" % old_fd)
		os.close(old_fd)
		# where_art_thy_filehandles()
		self.filehandle = old_filehandle
		# where_art_thy_filehandles()
		# print_to_tty("EXIT RESTORE %d" % self.fd)
