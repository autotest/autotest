#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
Miscellaneous small functions.
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import atexit, os, select, shutil, signal, StringIO, subprocess, tempfile
import time, types, urllib, re, sys, textwrap
import hosts
from common.error import *

# A dictionary of pid and a list of tmpdirs for that pid
__tmp_dirs = {}


def sh_escape(command):
	"""
	Escape special characters from a command so that it can be passed 
	as a double quoted (" ") string in a (ba)sh command.

	Args:
		command: the command string to escape. 

	Returns:
		The escaped command string. The required englobing double 
		quotes are NOT added and so should be added at some point by 
		the caller.

	See also: http://www.tldp.org/LDP/abs/html/escapingsection.html
	"""
	command= command.replace("\\", "\\\\")
	command= command.replace("$", r'\$')
	command= command.replace('"', r'\"')
	command= command.replace('`', r'\`')
	return command


def scp_remote_escape(filename):
	"""
	Escape special characters from a filename so that it can be passed 
	to scp (within double quotes) as a remote file.

	Bis-quoting has to be used with scp for remote files, "bis-quoting" 
	as in quoting x 2
	scp does not support a newline in the filename

	Args:
		filename: the filename string to escape. 

	Returns:
		The escaped filename string. The required englobing double 
		quotes are NOT added and so should be added at some point by 
		the caller.
	"""
	escape_chars= r' !"$&' "'" r'()*,:;<=>?[\]^`{|}'

	new_name= []
	for char in filename:
		if char in escape_chars:
			new_name.append("\\%s" % (char,))
		else:
			new_name.append(char)

	return sh_escape("".join(new_name))


def get(location, local_copy = False):
	"""Get a file or directory to a local temporary directory.

	Args:
		location: the source of the material to get. This source may 
			be one of:
			* a local file or directory
			* a URL (http or ftp)
			* a python file-like object

	Returns:
		The location of the file or directory where the requested
		content was saved. This will be contained in a temporary 
		directory on the local host. If the material to get was a 
		directory, the location will contain a trailing '/'
	"""
	tmpdir = get_tmp_dir()

	# location is a file-like object
	if hasattr(location, "read"):
		tmpfile = os.path.join(tmpdir, "file")
		tmpfileobj = file(tmpfile, 'w')
		shutil.copyfileobj(location, tmpfileobj)
		tmpfileobj.close()
		return tmpfile

	if isinstance(location, types.StringTypes):
		# location is a URL
		if location.startswith('http') or location.startswith('ftp'):
			tmpfile = os.path.join(tmpdir, os.path.basename(location))
			urllib.urlretrieve(location, tmpfile)
			return tmpfile
		# location is a local path
		elif os.path.exists(os.path.abspath(location)):
			if not local_copy:
				if os.path.isdir(location):
					return location.rstrip('/') + '/'
				else:
					return location
			tmpfile = os.path.join(tmpdir, os.path.basename(location))
			if os.path.isdir(location):
				tmpfile += '/'
				shutil.copytree(location, tmpfile, symlinks=True)
				return tmpfile
			shutil.copyfile(location, tmpfile)
			return tmpfile
		# location is just a string, dump it to a file
		else:
			tmpfd, tmpfile = tempfile.mkstemp(dir=tmpdir)
			tmpfileobj = os.fdopen(tmpfd, 'w')
			tmpfileobj.write(location)
			tmpfileobj.close()
			return tmpfile


def __nuke_subprocess(subproc):
       # the process has not terminated within timeout,
       # kill it via an escalating series of signals.
       signal_queue = [signal.SIGTERM, signal.SIGKILL]
       for sig in signal_queue:
	       try:
		       os.kill(subproc.pid, sig)
	       # The process may have died before we could kill it.
	       except OSError:
		       pass

	       for i in range(5):
		       rc = subproc.poll()
		       if rc != None:
			       return
		       time.sleep(1)


def _process_output(pipe, fbuffer, teefile=None, use_os_read=True):
	if use_os_read:
		data = os.read(pipe.fileno(), 1024)
	else:
		data = pipe.read()
	fbuffer.write(data)
	if teefile:
		teefile.write(data)
		teefile.flush()


def _wait_for_command(subproc, start_time, timeout, stdout_file, stderr_file,
		      stdout_tee, stderr_tee):
	if timeout:
		stop_time = start_time + timeout
		time_left = stop_time - time.time()
	else:
		time_left = None # so that select never times out
	while not timeout or time_left > 0:
		# select will return when stdout is ready (including when it is
		# EOF, that is the process has terminated).
		ready, _, _ = select.select([subproc.stdout, subproc.stderr],
					     [], [], time_left)
		# os.read() has to be used instead of
		# subproc.stdout.read() which will otherwise block
		if subproc.stdout in ready:
			_process_output(subproc.stdout, stdout_file,
					stdout_tee)
		if subproc.stderr in ready:
			_process_output(subproc.stderr, stderr_file,
					stderr_tee)

		pid, exit_status_indication = os.waitpid(subproc.pid,
							 os.WNOHANG)
		if pid:
			return exit_status_indication
		if timeout:
			time_left = stop_time - time.time()

	# the process has not terminated within timeout,
	# kill it via an escalating series of signals.
	if not pid:
		__nuke_subprocess(subproc)
	raise AutoservRunError('Command not complete within %s seconds'
			       % timeout)


def run(command, timeout=None, ignore_status=False,
	stdout_tee=None, stderr_tee=None):
	"""
	Run a command on the host.

	Args:
		command: the command line string
		timeout: time limit in seconds before attempting to
			kill the running process. The run() function
			will take a few seconds longer than 'timeout'
			to complete if it has to kill the process.
		ignore_status: do not raise an exception, no matter what
			the exit code of the command is.
		stdout_tee: optional file-like object to which stdout data
		            will be written as it is generated (data will still
			    be stored in result.stdout)
		stderr_tee: likewise for stderr

	Returns:
		a CmdResult object

	Raises:
		AutoservRunError: the exit code of the command
			execution was not 0
	"""
	result = CmdResult(command)
	sp = subprocess.Popen(command, stdout=subprocess.PIPE,
			      stderr=subprocess.PIPE, close_fds=True,
			      shell=True, executable="/bin/bash")
	stdout_file = StringIO.StringIO()
	stderr_file = StringIO.StringIO()

	try:
		# We are holding ends to stdin, stdout pipes
		# hence we need to be sure to close those fds no mater what
		start_time = time.time()
		result.exit_status = _wait_for_command(sp, start_time, timeout,
			      stdout_file, stderr_file, stdout_tee, stderr_tee)

		result.duration = time.time() - start_time
		# don't use os.read now, so we get all the rest of the output
		_process_output(sp.stdout, stdout_file, stdout_tee,
				use_os_read=False)
		_process_output(sp.stderr, stderr_file, stderr_tee,
				use_os_read=False)
	finally:
		# close our ends of the pipes to the sp no matter what
		sp.stdout.close()
		sp.stderr.close()

	result.stdout = stdout_file.getvalue()
	result.stderr = stderr_file.getvalue()

	if not ignore_status and result.exit_status > 0:
		raise AutoservRunError("command execution error", result)

	return result


def system(command, timeout=None, ignore_status=False):
	return run(command, timeout, ignore_status).exit_status


def system_output(command, timeout=None, ignore_status=False):
	return run(command, timeout, ignore_status).stdout


def get_tmp_dir():
	"""Return the pathname of a directory on the host suitable 
	for temporary file storage.

	The directory and its content will be deleted automatically
	at the end of the program execution if they are still present.
	"""
	global __tmp_dirs

	dir_name= tempfile.mkdtemp(prefix="autoserv-")
	pid = os.getpid()
	if not pid in __tmp_dirs:
		__tmp_dirs[pid] = []
	__tmp_dirs[pid].append(dir_name)
	return dir_name


@atexit.register
def __clean_tmp_dirs():
	"""Erase temporary directories that were created by the get_tmp_dir() 
	function and that are still present.
	"""
	global __tmp_dirs

	pid = os.getpid()
	if pid not in __tmp_dirs:
		return
	for dir in __tmp_dirs[pid]:
		try:
			shutil.rmtree(dir)
		except OSError, e:
			if e.errno == 2:
				pass
	__tmp_dirs[pid] = []


def unarchive(host, source_material):
	"""Uncompress and untar an archive on a host.

	If the "source_material" is compresses (according to the file 
	extension) it will be uncompressed. Supported compression formats 
	are gzip and bzip2. Afterwards, if the source_material is a tar 
	archive, it will be untarred.

	Args:
		host: the host object on which the archive is located
		source_material: the path of the archive on the host

	Returns:
		The file or directory name of the unarchived source material. 
		If the material is a tar archive, it will be extracted in the
		directory where it is and the path returned will be the first
		entry in the archive, assuming it is the topmost directory.
		If the material is not an archive, nothing will be done so this
		function is "harmless" when it is "useless".
	"""
	# uncompress
	if (source_material.endswith(".gz") or 
		source_material.endswith(".gzip")):
		host.run('gunzip "%s"' % (sh_escape(source_material)))
		source_material= ".".join(source_material.split(".")[:-1])
	elif source_material.endswith("bz2"):
		host.run('bunzip2 "%s"' % (sh_escape(source_material)))
		source_material= ".".join(source_material.split(".")[:-1])

	# untar
	if source_material.endswith(".tar"):
		retval= host.run('tar -C "%s" -xvf "%s"' % (
			sh_escape(os.path.dirname(source_material)),
			sh_escape(source_material),))
		source_material= os.path.join(os.path.dirname(source_material), 
			retval.stdout.split()[0])

	return source_material


def write_keyval(dirname, dictionary):
	keyval = open(os.path.join(dirname, 'keyval'), 'w')
	for key in dictionary.keys():
		value = '%s' % dictionary[key]     # convert numbers to strings
		if re.search(r'\W', key):
			raise 'Invalid key: ' + key
		keyval.write('%s=%s\n' % (key, str(value)))
	keyval.close()


def update_version(srcdir, preserve_srcdir, new_version, install, *args, **dargs):
	"""
	Make sure srcdir is version new_version

	If not, delete it and install() the new version.

	In the preserve_srcdir case, we just check it's up to date,
	and if not, we rerun install, without removing srcdir
	"""
	versionfile = srcdir + '/.version'
	install_needed = True

	if os.path.exists(srcdir):
		if os.path.exists(versionfile):
			old_version = pickle.load(open(versionfile, 'r'))
			if (old_version == new_version):
				install_needed = False

	if install_needed:
		if not preserve_srcdir:
			system('rm -rf ' + srcdir)
		install(*args, **dargs)
		if os.path.exists(srcdir):
			pickle.dump(new_version, open(versionfile, 'w'))


def get_server_dir():
	path = os.path.dirname(sys.modules['utils'].__file__)
	return os.path.abspath(path)


def find_pid(command):
	for line in system_output('ps -eo pid,cmd').rstrip().split('\n'):
		(pid, cmd) = line.split(None, 1)
		if re.search(command, cmd):
			return int(pid)
	return None


def nohup(command, stdout='/dev/null', stderr='/dev/null', background=True,
								env = {}):
	cmd = ' '.join(key+'='+val for key, val in env.iteritems())
	cmd += ' nohup ' + command
	cmd += ' > %s' % stdout
	if stdout == stderr:
		cmd += ' 2>&1'
	else:
		cmd += ' 2> %s' % stderr
	if background:
		cmd += ' &'
	system(cmd)


class AutoservOptionParser:
	"""Custom command-line options parser for autoserv.

	We can't use the general getopt methods here, as there will be unknown
	extra arguments that we pass down into the control file instead.
	Thus we process the arguments by hand, for which we are duly repentant.
	Making a single function here just makes it harder to read. Suck it up.
	"""

	def __init__(self, args):
		self.args = args


	def parse_opts(self, flag):
		if self.args.count(flag):
			idx = self.args.index(flag)
			self.args[idx : idx+1] = []
			return True
		else:
			return False


	def parse_opts_param(self, flag, default = None, split = False):
		if self.args.count(flag):
			idx = self.args.index(flag)
			ret = self.args[idx+1]
			self.args[idx : idx+2] = []
			if split:
				return ret.split(split)
			else:
				return ret
		else:
			return default


class CmdResult(object):
	"""
	Command execution result.

	command:     String containing the command line itself
	exit_status: Integer exit code of the process
	stdout:      String containing stdout of the process
	stderr:      String containing stderr of the process
	duration:    Elapsed wall clock time running the process
	"""

	def __init__(self, command = None):
		self.command = command
		self.exit_status = None
		self.stdout = ""
		self.stderr = ""
		self.duration = 0


	def __repr__(self):
		wrapper = textwrap.TextWrapper(width = 78, 
					       initial_indent="\n    ",
					       subsequent_indent="    ")
		
		stdout = self.stdout.rstrip()
		if stdout:
			stdout = "\nstdout:\n%s" % stdout
		
		stderr = self.stderr.rstrip()
		if stderr:
			stderr = "\nstderr:\n%s" % stderr
		
		return ("* Command: %s\n"
			"Exit status: %s\n"
			"Duration: %s\n"
			"%s"
			"%s"
			% (wrapper.fill(self.command), self.exit_status, 
			self.duration, stdout, stderr))
