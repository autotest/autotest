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

import installable_object
import errors
import utils


AUTOTEST_SVN  = 'svn://test.kernel.org/autotest/trunk/client'
AUTOTEST_HTTP = 'http://test.kernel.org/svn/autotest/trunk/client'

# Timeouts for powering down and up respectively
HALT_TIME = 300
BOOT_TIME = 300


class AutotestRunError(errors.AutoservRunError):
	pass


class Autotest(installable_object.InstallableObject):
	"""
	This class represents the Autotest program.

	Autotest is used to run tests automatically and collect the results.
	It also supports profilers.

	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must
	implement the unimplemented methods in parent classes.
	"""
	def __init__(self, host = None):
		self.host = host
		self.got = False
		self.installed = False
		path = os.path.dirname(sys.modules['server_job'].__file__)
		self.serverdir = os.path.abspath(path)
		super(Autotest, self).__init__()


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
		host.ensure_up()
		host.setup()
		print "Installing autotest on %s" % host.hostname
		# try to install from file or directory
		if self.source_material:
			if os.path.isdir(self.source_material):
				# Copy autotest recursively
				autodir = _get_autodir(host)
				host.run('mkdir -p "%s"' %
						utils.sh_escape(autodir))
				host.send_file(self.source_material,
						autodir)
			else:
				# Copy autotest via tarball
				raise "Not yet implemented!"
			print "Installation of autotest completed"
			self.installed = True
			return

		# if that fails try to install using svn
		if utils.run('which svn').exit_status:
			raise AutoservError('svn not found in path on \
			target machine: %s' % host.name)
		try:
			host.run('svn checkout %s %s' %
				 (AUTOTEST_SVN, _get_autodir(host)))
		except errors.AutoservRunError, e:
			host.run('svn checkout %s %s' %
				 (AUTOTEST_HTTP, _get_autodir(host)))
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


	def run(self, control_file, results_dir = '.', host = None):
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

		host.ensure_up()
		
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
		host.run('rm -f ' + atrun.remote_control_file)
		host.run('rm -f ' + atrun.remote_control_file + '.state')
		
		# Copy control_file to remote_control_file on the host
		tmppath = utils.get(control_file)
		host.send_file(tmppath, atrun.remote_control_file)
		os.remove(tmppath)
		
		atrun.execute_control()
		
		# retrive results
		results = os.path.join(atrun.autodir, 'results', 'default')
		# Copy all dirs in default to results_dir
		host.get_file(results + '/', results_dir)


	def run_test(self, test_name, results_dir = '.', host = None, \
								*args, **dargs):
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
		self.run(control, results_dir, host)


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
		self.env = ''
		if hasattr(host, 'env'):
			self.env = host.env
		
		self.autodir = _get_autodir(self.host)
		self.remote_control_file = os.path.join(self.autodir, 'control')


	def verify_machine(self):
		binary = os.path.join(self.autodir, 'bin/autotest')
		try:
			self.host.run('ls ' + binary)
		except:
			raise "Autotest does not appear to be installed"
		tmpdir = os.path.join(self.autodir, 'tmp')
		self.host.run('umount %s' % tmpdir, ignore_status=True)


	def __execute_section(self, section):
		print "Executing %s/bin/autotest %s/control phase %d" % \
					(self.autodir, self.autodir,
					 section)
		logfile = "%s/debug/client.log.%d" % (self.results_dir,
						      section)
		client_log = open(logfile, 'w')
		if section > 0:
			cont = '-c'
		else:
			cont = ''
		client = os.path.join(self.autodir, 'bin/autotest_client')
		ssh = "ssh -q %s@%s" % (self.host.user, self.host.hostname)
		cmd = "%s %s %s" % (client, cont, self.remote_control_file)
		print "%s '%s %s'" % (ssh, self.env, cmd)
		# Use Popen here, not m.ssh, as we want it in the background
		p = subprocess.Popen("%s '%s %s'" % (ssh, self.env, cmd),
				     shell=True,
				     stdout=client_log,
				     stderr=subprocess.PIPE)
		line = None
		for line in iter(p.stderr.readline, ''):
			print line,
			sys.stdout.flush()
		if not line:
			raise AutotestRunError("execute_section: %s '%s' \
			failed to return anything" % (ssh, cmd))
		return line


	def execute_control(self):
		section = 0
		while True:
			last = self.__execute_section(section)
			section += 1
			if re.match('DONE', last):
				print "Client complete"
				return
			elif re.match('REBOOT', last):
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
					if hasattr(self.host, 'hardreset'):
						print "Hardresetting %s" % (
							self.host.hostname,)
						self.host.hardreset()
					raise AutotestRunError("%s failed to "
						"boot after %ds" % (
						self.host.hostname,
						BOOT_TIME,))
				continue
			raise AutotestRunError("Aborting - unknown "
				"return code: %s\n" % last)


def _get_autodir(host):
	try:
		atdir = host.run(
			'grep "autodir *=" /etc/autotest.conf').stdout.strip()
		if atdir:
			m = re.search(r'autodir *= *[\'"]?([^\'"]*)[\'"]?',
				      atdir)
			return m.group(1)
	except errors.AutoservRunError:
		pass
	for path in ['/usr/local/autotest', '/home/autotest']:
		try:
			host.run('ls ' + path)
			return path
		except errors.AutoservRunError:
			pass
	raise AutotestRunError("Cannot figure out autotest directory")
