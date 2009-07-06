""" Parallel execution management """

__author__ = """Copyright Andy Whitcroft 2006"""

import sys, os, pickle, logging
from autotest_lib.client.common_lib import error

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
        except error.AutotestError:
            raise
        except Exception, e:
            raise error.UnhandledTestError(e)
    except Exception, detail:
        try:
            try:
                logging.error("child process failed")
            finally:
                ename = tmp + "/debug/error-%d" % (os.getpid())
                pickle.dump(detail, open(ename, "w"))
                sys.stdout.flush()
                sys.stderr.flush()
        finally:
            os._exit(1)
    else:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(0)


def fork_waitfor(tmp, pid):
    (pid, status) = os.waitpid(pid, 0)

    ename = tmp + "/debug/error-%d" % pid
    if os.path.exists(ename):
        raise pickle.load(file(ename, 'r'))

    if status:
        raise error.TestError("Test subprocess failed rc=%d" % (status))
