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


import atexit
import os
import os.path
import select
import shutil
import signal
import StringIO
import subprocess
import tempfile
import time
import types
import urllib

import hosts
import errors


__tmp_dirs= []


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


def get(location):
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


def run(command, timeout=None, ignore_status=False):
	"""
	Run a command on the host.

	Args:
		command: the command line string
		timeout: time limit in seconds before attempting to 
			kill the running process. The run() function
			will take a few seconds longer than 'timeout'
			to complete if it has to kill the process.

	Returns:
		a hosts.CmdResult object

	Raises:
		AutoservRunError: the exit code of the command 
			execution was not 0

	TODO(poirier): Add a "tee" option to send the command's 
		stdout and stderr to python's stdout and stderr? At 
		the moment, there is no way to see the command's 
		output as it is running.
	TODO(poirier): Should a timeout raise an exception? Should
		exceptions be raised at all?
	"""
	result= hosts.CmdResult()
	result.command= command
	sp= subprocess.Popen(command, stdout=subprocess.PIPE, 
		stderr=subprocess.PIPE, close_fds=True, shell=True, 
		executable="/bin/bash")

	try:
		# We are holding ends to stdin, stdout pipes
		# hence we need to be sure to close those fds no mater what
		start_time= time.time()
		if timeout:
			stop_time= start_time + timeout
			time_left= stop_time - time.time()
			while time_left > 0:
				# select will return when stdout is ready 
				# (including when it is EOF, that is the 
				# process has terminated).
				(retval, tmp, tmp) = select.select(
					[sp.stdout], [], [], time_left)
				if len(retval):
					# os.read() has to be used instead of 
					# sp.stdout.read() which will 
					# otherwise block
					result.stdout += os.read(
						sp.stdout.fileno(), 1024)

				(pid, exit_status_indication) = os.waitpid(
					sp.pid, os.WNOHANG)
				if pid:
					stop_time= time.time()
				time_left= stop_time - time.time()

			# the process has not terminated within timeout, 
			# kill it via an escalating series of signals.
			if not pid:
				signal_queue = [signal.SIGTERM, signal.SIGKILL]
				for sig in signal_queue:
					try:
						os.kill(sp.pid, sig)
					# handle race condition in which 
					# process died before we could kill it.
					except OSError:
						pass

					for i in range(5):
						(pid, exit_status_indication
							) = os.waitpid(sp.pid, 
							os.WNOHANG)
						if pid:
							break
						else:
							time.sleep(1)
					if pid:
						break
		else:
			exit_status_indication = os.waitpid(sp.pid, 0)[1]

		result.duration = time.time() - start_time
		result.aborted = exit_status_indication & 127
		if result.aborted:
			result.exit_status= None
		else:
			result.exit_status=  exit_status_indication / 256
		result.stdout += sp.stdout.read()
		result.stderr = sp.stderr.read()

	finally:
		# close our ends of the pipes to the sp no matter what
		sp.stdout.close()
		sp.stderr.close()

	if not ignore_status and result.exit_status > 0:
		raise errors.AutoservRunError("command execution error", 
			result)

	return result


def get_tmp_dir():
	"""Return the pathname of a directory on the host suitable 
	for temporary file storage.

	The directory and its content will be deleted automatically
	at the end of the program execution if they are still present.
	"""
	global __tmp_dirs

	dir_name= tempfile.mkdtemp(prefix="autoserv-")
	__tmp_dirs.append(dir_name)
	return dir_name


@atexit.register
def __clean_tmp_dirs():
	"""Erase temporary directories that were created by the get_tmp_dir() 
	function and that are still present.
	"""
	global __tmp_dirs

	for dir in __tmp_dirs:
		shutil.rmtree(dir)
	__tmp_dirs= []


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
