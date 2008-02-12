#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Autotest class

	Autotest: software to run tests automatically
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import re
import os
import sys
import subprocess
import urllib
import tempfile
import shutil
import time

import installable_object
import utils
from common import logging
from common.error import *


AUTOTEST_SVN  = 'svn://test.kernel.org/autotest/trunk/client'
AUTOTEST_HTTP = 'http://test.kernel.org/svn/autotest/trunk/client'

# Timeouts for powering down and up respectively
HALT_TIME = 300
BOOT_TIME = 1800





class Autotest(installable_object.InstallableObject):
	"""
	This class represents the Autotest program.

	Autotest is used to run tests automatically and collect the results.
	It also supports profilers.

	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must
	implement the unimplemented methods in parent classes.
	"""
	job = None


	def __init__(self, host = None):
		self.host = host
		self.got = False
		self.installed = False
		self.serverdir = utils.get_server_dir()
		super(Autotest, self).__init__()


	@logging.record
	def install(self, host = None):
		"""
		Install autotest.  If get() was not called previously, an 
		attempt will be made to install from the autotest svn 
		repository.
		
		Args:
			host: a Host instance on which autotest will be
				installed
		
		Raises:
			AutoservError: if a tarball was not specified and
				the target host does not have svn installed in its path
		
		TODO(poirier): check dependencies
		autotest needs:
		bzcat
		liboptdev (oprofile)
		binutils-dev (oprofile)
		make
		psutils (netperf)
		"""
		if not host:
			host = self.host
		if not self.got:
			self.get()
		host.wait_up(timeout=30)
		host.setup()
		print "Installing autotest on %s" % host.hostname

		autodir = _get_autodir(host)
		host.run('mkdir -p "%s"' % utils.sh_escape(autodir))

		if getattr(host, 'site_install_autotest', None):
			if host.site_install_autotest():
				self.installed = True
				return

		# try to install from file or directory
		if self.source_material:
			if os.path.isdir(self.source_material):
				# Copy autotest recursively
				host.send_file(self.source_material, autodir)
			else:
				# Copy autotest via tarball
				e_msg = 'Installation method not yet implemented!'
				raise NotImplementedError(e_msg)
			print "Installation of autotest completed"
			self.installed = True
			return

		# if that fails try to install using svn
		if utils.run('which svn').exit_status:
			raise AutoservError('svn not found in path on \
			target machine: %s' % host.name)
		try:
			host.run('svn checkout %s %s' %
				 (AUTOTEST_SVN, autodir))
		except AutoservRunError, e:
			host.run('svn checkout %s %s' %
				 (AUTOTEST_HTTP, autodir))
		print "Installation of autotest completed"
		self.installed = True


	def get(self, location = None):
		if not location:
			location = os.path.join(self.serverdir, '../client')
			location = os.path.abspath(location)
		# If there's stuff run on our client directory already, it
		# can cause problems. Try giving it a quick clean first.
		cwd = os.getcwd()
		os.chdir(location)
		os.system('tools/make_clean')
		os.chdir(cwd)
		super(Autotest, self).get(location)
		self.got = True


	def run(self, control_file, results_dir = '.', host = None,
		timeout=None):
		"""
		Run an autotest job on the remote machine.
		
		Args:
			control_file: an open file-like-obj of the control file
			results_dir: a str path where the results should be stored
				on the local filesystem
			host: a Host instance on which the control file should
				be run
		
		Raises:
			AutotestRunError: if there is a problem executing
				the control file
		"""
		results_dir = os.path.abspath(results_dir)
		if not host:
			host = self.host
		if not self.installed:
			self.install(host)

		host.wait_up(timeout=30)
		
		atrun = _Run(host, results_dir)
		try:
			atrun.verify_machine()
		except:
			print "Verify machine failed on %s. Reinstalling" % \
								host.hostname
			self.install(host)
		atrun.verify_machine()
		debug = os.path.join(results_dir, 'debug')
		try:
			os.makedirs(debug)
		except:
			pass
		
		# Ready .... Aim ....
		for control in [atrun.remote_control_file,
				atrun.remote_control_file + '.state',
				atrun.manual_control_file,
				atrun.manual_control_file + '.state']:
			host.run('rm -f ' + control)
		
		# Copy control_file to remote_control_file on the host
		tmppath = utils.get(control_file)
		host.send_file(tmppath, atrun.remote_control_file)
		if os.path.abspath(tmppath) != os.path.abspath(control_file):
			os.remove(tmppath)

		try:
			atrun.execute_control(timeout=timeout)
		finally:
			# make an effort to wait for the machine to come up
			try:
				host.wait_up(timeout=30)
			except AutoservError:
				# don't worry about any errors, we'll try and
				# get the results anyway
				pass

			# get the results
			results = os.path.join(atrun.autodir, 'results',
					       'default')
			# Copy all dirs in default to results_dir
			host.get_file(results + '/', results_dir)


	def run_timed_test(self, test_name, results_dir = '.', host = None,
			   timeout=None, *args, **dargs):
		"""
		Assemble a tiny little control file to just run one test,
		and run it as an autotest client-side test
		"""
		if not host:
			host = self.host
		if not self.installed:
			self.install(host)
		opts = ["%s=%s" % (o[0], repr(o[1])) for o in dargs.items()]
		cmd = ", ".join([repr(test_name)] + map(repr, args) + opts)
		control = "job.run_test(%s)\n" % cmd
		self.run(control, results_dir, host, timeout=timeout)


	def run_test(self, test_name, results_dir = '.', host = None,
		     *args, **dargs):
		self.run_timed_test(test_name, results_dir, host, None,
				    *args, **dargs)


# a file-like object for catching stderr from the autotest client and
# extracting status logs from it
class StdErrRedirector(object):
	"""Partial file object to write to both stdout and
	the status log file.  We only implement those methods
	utils.run() actually calls.
	"""
	parser = re.compile(r"^AUTOTEST_STATUS:([^:]*):(.*)$")

	def __init__(self, status_log):
		self.status_log = status_log
		self.leftover = ""
		self.last_line = ""
		self.logs = {}


	def _process_log_dict(self, log_dict):
		log_list = log_dict.pop("logs", [])
		for key in sorted(log_dict.iterkeys()):
			log_list += self._process_log_dict(log_dict.pop(key))
		return log_list


	def _process_logs(self):
		"""Go through the accumulated logs in self.log and print them
		out to stdout and the status log. Note that this processes
		logs in an ordering where:

		1) logs to different tags are never interleaved
		2) logs to x.y come before logs to x.y.z for all z
		3) logs to x.y come before x.z whenever y < z

		Note that this will in general not be the same as the
		chronological ordering of the logs. However, if a chronological
		ordering is desired that one can be reconstructed from the
		status log by looking at timestamp lines."""
		log_list = self._process_log_dict(self.logs)
		for line in log_list:
			print >> self.status_log, line
		if log_list:
			self.last_line = log_list[-1]


	def _process_quoted_line(self, tag, line):
		"""Process a line quoted with an AUTOTEST_STATUS flag. If the
		tag is blank then we want to push out all the data we've been
		building up in self.logs, and then the newest line. If the
		tag is not blank, then push the line into the logs for handling
		later."""
		print line
		if tag == "":
			self._process_logs()
			print >> self.status_log, line
			self.last_line = line
		else:
			tag_parts = [int(x) for x in tag.split(".")]
			log_dict = self.logs
			for part in tag_parts:
				log_dict = log_dict.setdefault(part, {})
			log_list = log_dict.setdefault("logs", [])
			log_list.append(line)


	def _process_line(self, line):
		"""Write out a line of data to the appropriate stream. Status
		lines sent by autotest will be prepended with
		"AUTOTEST_STATUS", and all other lines are ssh error
		messages."""
		match = self.parser.search(line)
		if match:
			tag, line = match.groups()
			self._process_quoted_line(tag, line)
		else:
			print >> sys.stderr, line


	def write(self, data):
		data = self.leftover + data
		lines = data.split("\n")
		# process every line but the last one
		for line in lines[:-1]:
			self._process_line(line)
		# save the last line for later processing
		# since we may not have the whole line yet
		self.leftover = lines[-1]


	def flush(self):
		sys.stdout.flush()
		sys.stderr.flush()
		self.status_log.flush()


	def close(self):
		if self.leftover:
			self._process_line(self.leftover)
			self._process_logs()
			self.flush()


class _Run(object):
	"""
	Represents a run of autotest control file.  This class maintains
	all the state necessary as an autotest control file is executed.

	It is not intended to be used directly, rather control files
	should be run using the run method in Autotest.
	"""
	def __init__(self, host, results_dir):
		self.host = host
		self.results_dir = results_dir
		self.env = host.env

		self.autodir = _get_autodir(self.host)
		self.manual_control_file = os.path.join(self.autodir, 'control')
		self.remote_control_file = os.path.join(self.autodir,
							     'control.autoserv')


	def verify_machine(self):
		binary = os.path.join(self.autodir, 'bin/autotest')
		try:
			self.host.run('ls %s > /dev/null 2>&1' % binary)
		except:
			raise "Autotest does not appear to be installed"
		tmpdir = os.path.join(self.autodir, 'tmp')
		self.host.run('umount %s' % tmpdir, ignore_status=True)


	def __execute_section(self, section, timeout):
		print "Executing %s/bin/autotest %s/control phase %d" % \
					(self.autodir, self.autodir,
					 section)

		# build up the full command we want to run over the host
		cmd = [os.path.join(self.autodir, 'bin/autotest_client')]
		if section > 0:
			cmd.append('-c')
		cmd.append(self.remote_control_file)
		full_cmd = ' '.join(cmd)

		# open up the files we need for our logging
		client_log_file = os.path.join(self.results_dir, 'debug',
					       'client.log.%d' % section)
		client_log = open(client_log_file, 'w', 0)
		status_log_file = os.path.join(self.results_dir, 'status.log')
		status_log = open(status_log_file, 'a', 0)

		try:
			redirector = StdErrRedirector(status_log)
			result = self.host.run(full_cmd, ignore_status=True,
					       timeout=timeout,
					       stdout_tee=client_log,
					       stderr_tee=redirector)
		finally:
			redirector.close()

		if result.exit_status == 1:
			self.host.job.aborted = True
		if not result.stderr:
  			raise AutotestRunError(
			    "execute_section: %s failed to return anything\n"
			    "stdout:%s\n" % (full_cmd, result.stdout))

		return redirector.last_line


	def execute_control(self, timeout=None):
		section = 0
		time_left = None
		if timeout:
			end_time = time.time() + timeout
			time_left = end_time - time.time()
		while not timeout or time_left > 0:
			last = self.__execute_section(section, time_left)
			if timeout:
				time_left = end_time - time.time()
				if time_left <= 0:
					break
			section += 1
			if re.match(r'^END .*\t----\t----\t.*$', last):
				print "Client complete"
				return
			elif re.match('^\t*GOOD\t----\treboot\.start.*$', last):
				print "Client is rebooting"
				print "Waiting for client to halt"
				if not self.host.wait_down(HALT_TIME):
					raise AutotestRunError("%s \
					failed to shutdown after %ds" %
							(self.host.hostname,
							HALT_TIME))
				print "Client down, waiting for restart"
				if not self.host.wait_up(BOOT_TIME):
					# since reboot failed
					# hardreset the machine once if possible
					# before failing this control file
					print "Hardresetting %s" % (
					    self.host.hostname,)
					try:
						self.host.hardreset(wait=False)
					except AutoservUnsupportedError:
						print "Hardreset unsupported on %s" % (
						    self.host.hostname,)
					raise AutotestRunError("%s failed to "
						"boot after %ds" % (
						self.host.hostname,
						BOOT_TIME,))
				continue
			raise AutotestRunError("Aborting - unknown "
				"return code: %s\n" % last)

		# should only get here if we timed out
		assert timeout
		raise AutotestTimeoutError()


def _get_autodir(host):
	dir = host.get_autodir()
	if dir:
		return dir
	try:
		# There's no clean way to do this. readlink may not exist
		cmd = "python -c 'import os,sys; print os.readlink(sys.argv[1])' /etc/autotest.conf 2> /dev/null"
		dir = os.path.dirname(host.run(cmd).stdout)
		if dir:
			return dir
	except AutoservRunError:
		pass
	for path in ['/usr/local/autotest', '/home/autotest']:
		try:
			host.run('ls %s > /dev/null 2>&1' % \
					 os.path.join(path, 'bin/autotest'))
			return path
		except AutoservRunError:
			pass
	raise AutotestRunError("Cannot figure out autotest directory")
