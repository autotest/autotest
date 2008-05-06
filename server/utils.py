#!/usr/bin/python
#
# Copyright 2008 Google Inc. Released under the GPL v2

"""
Miscellaneous small functions.
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import atexit, os, re, shutil, textwrap, sys, tempfile, types, urllib

from autotest_lib.client.common_lib.utils import *


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


def get_server_dir():
	path = os.path.dirname(sys.modules['autotest_lib.server.utils'].__file__)
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


def default_mappings(machines):
	"""
	Returns a simple mapping in which all machines are assigned to the
	same key.  Provides the default behavior for 
	form_ntuples_from_machines. """
	mappings = {}
	failures = []
	
	mach = machines[0]
	mappings['ident'] = [mach]
	if len(machines) > 1:	
		machines = machines[1:]
		for machine in machines:
			mappings['ident'].append(machine)
		
	return (mappings, failures)


def form_ntuples_from_machines(machines, n=2, mapping_func=default_mappings):
	"""Returns a set of ntuples from machines where the machines in an
	   ntuple are in the same mapping, and a set of failures which are
	   (machine name, reason) tuples."""
	ntuples = []
	(mappings, failures) = mapping_func(machines)
	
	# now run through the mappings and create n-tuples.
	# throw out the odd guys out
	for key in mappings:
		key_machines = mappings[key]
		total_machines = len(key_machines)

		# form n-tuples 
		while len(key_machines) >= n:
			ntuples.append(key_machines[0:n])
			key_machines = key_machines[n:]

		for mach in key_machines:
			failures.append((mach, "machine can not be tupled"))

	return (ntuples, failures)


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
