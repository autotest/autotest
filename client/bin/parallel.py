""" Parallel execution management """

__author__ = """Copyright Andy Whitcroft 2006"""

import sys, logging, os, pickle, traceback
from autotest_lib.client.common_lib import error, utils

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
                logging.error('child process failed')
                # logging.exception() uses ERROR level, but we want DEBUG for
                # the traceback
                logging.debug(traceback.format_exc())
            finally:
                # note that exceptions originating in this block won't make it
                # to the logs
                output_dir = os.path.join(tmp, 'debug')
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                ename = os.path.join(output_dir, "error-%d" % os.getpid())
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


def _check_for_subprocess_exception(temp_dir, pid):
    ename = temp_dir + "/debug/error-%d" % pid
    if os.path.exists(ename):
        raise pickle.load(file(ename, 'r'))


def fork_waitfor(tmp, pid):
    (pid, status) = os.waitpid(pid, 0)

    _check_for_subprocess_exception(tmp, pid)

    if status:
        raise error.TestError("Test subprocess failed rc=%d" % (status))


def fork_nuke_subprocess(tmp, pid):
    utils.nuke_pid(pid)
    _check_for_subprocess_exception(tmp, pid)
