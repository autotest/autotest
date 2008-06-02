__author__ = "raphtee@google.com (Travis Miller)"


import sys


usage = """\
usage: autoserv
	[-h, --help]               # This help message
	[-m machine,[machine,...]] # list of machines to pass to control file
	[-M machines_file]         # list of machines (from a file)
	[-c]                       # control file is a client side control
	[-r resultsdir]            # specify results directory (default '.')
	[-i]                       # reinstall machines before running the job
	[-I]                       # reinstall machines after running the job
	[-b]                       # reboot all specified machines after the job
	[-l label]                 # label for the job (arbitrary string)
	[-u user]                  # username for the job (email address)
	[-v]                       # verify the machines only
	[-R]                       # repair the machines
	[-n]                       # no teeing the status to stdout/stderr
	[-p]                       # write pidfile (.autoserv_execute)
	[-P jobname]               # parse the results of the job
	<control file>             # name of the control file to run
	[args ...]                 # args to pass through to the control file
"""


class base_autoserv_parser(object):
	"""Custom command-line options parser for autoserv.

	We can't use the general getopt methods here, as there will be unknown
	extra arguments that we pass down into the control file instead.
	Thus we process the arguments by hand, for which we are duly repentant.
	Making a single function here just makes it harder to read. Suck it up.
	"""
	def __init__(self):
		self.args = sys.argv[1:]
		if len(self.args) == 0:
			print self.get_usage()
			sys.exit(1)
		if self.parse_opts('-h') or self.parse_opts('--help'):
			print self.get_usage()
			sys.exit(0)


	def get_usage(self):
		return usage


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



try:
	from autotest_lib.server.site_autoserv_parser \
	     import site_autoserv_parser
except ImportError:
	class site_autoserv_parser(base_autoserv_parser):
		pass


class autoserv_parser(site_autoserv_parser):
	pass


# create the one and only one instance of autoserv_parser
autoserv_parser = autoserv_parser()
