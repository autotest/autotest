""" Parallel execution management """

__author__ = """Copyright Andy Whitcroft 2006"""

import sys, os, pickle
from error import *

def fork_start(tmp, l):
	sys.stdout.flush()
	sys.stderr.flush()
	pid = os.fork()
	if pid:
		# Parent
		return pid

	try:
		try:
			l()

		except AutotestError:
			raise

		except:
			raise UnhandledError("test failed and threw:\n")

	except Exception, detail:
		ename = tmp + "/debug/error-%d" % (os.getpid())
		pickle.dump(detail, open(ename, "w"))

		sys.stdout.flush()
		sys.stderr.flush()
		os._exit(1)

	sys.stdout.flush()
	sys.stderr.flush()
	os._exit(0)


def fork_waitfor(tmp, pid):
	(pid, status) = os.waitpid(pid, 0)

	ename = tmp + "/debug/error-%d" % pid
	if (os.path.exists(ename)):
		raise pickle.load(file(ename, 'r'))

	if (status != 0):
		raise TestError("test failed rc=%d" % (status))
