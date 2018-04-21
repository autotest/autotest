""" Parallel execution management """

__author__ = """Copyright Andy Whitcroft 2006"""

import gc
import logging
import os
import pickle
import sys
import time
import traceback

from autotest.client.shared import error, utils


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
        except Exception as e:
            raise error.UnhandledTestError(e)
    except Exception as detail:
        try:
            try:
                logging.error('child process failed')
                # logging.exception() uses ERROR level, but we want DEBUG for
                # the traceback
                for line in traceback.format_exc().splitlines():
                    logging.debug(line)
            finally:
                # note that exceptions originating in this block won't make it
                # to the logs
                output_dir = os.path.join(tmp, 'debug')
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                ename = os.path.join(output_dir, "error-%d" % os.getpid())
                pickle.dump(detail, open(ename, "wb"))

                sys.stdout.flush()
                sys.stderr.flush()
        finally:
            # clear exception information to allow garbage collection of
            # objects referenced by the exception's traceback
            if sys.version_info < (3, 0):
                sys.exc_clear()
            gc.collect()
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
        try:
            e = pickle.load(open(ename, 'rb'))
        except ImportError:
            logging.error("Unknown exception to unpickle. Exception must be"
                          " defined in error module.")
            raise
        # rename the error-pid file so that they do not affect later child
        # processes that use recycled pids.
        i = 0
        while True:
            pename = ename + ('-%d' % i)
            i += 1
            if not os.path.exists(pename):
                break
        os.rename(ename, pename)
        raise e


def fork_waitfor(tmp, pid):
    (pid, status) = os.waitpid(pid, 0)

    _check_for_subprocess_exception(tmp, pid)

    if status:
        raise error.TestError("Test subprocess failed rc=%d" % (status))


def fork_waitfor_timed(tmp, pid, timeout):
    """
    Waits for pid until it terminates or timeout expires.
    If timeout expires, test subprocess is killed.
    """
    timer_expired = True
    poll_time = 2
    time_passed = 0
    while time_passed < timeout:
        time.sleep(poll_time)
        (child_pid, status) = os.waitpid(pid, os.WNOHANG)
        if (child_pid, status) == (0, 0):
            time_passed = time_passed + poll_time
        else:
            timer_expired = False
            break

    if timer_expired:
        logging.info('Timer expired (%d sec.), nuking pid %d', timeout, pid)
        utils.nuke_pid(pid)
        (child_pid, status) = os.waitpid(pid, 0)
        raise error.TestError("Test timeout expired, rc=%d" % (status))
    else:
        _check_for_subprocess_exception(tmp, pid)

    if status:
        raise error.TestError("Test subprocess failed rc=%d" % (status))


def fork_nuke_subprocess(tmp, pid):
    utils.nuke_pid(pid)
    _check_for_subprocess_exception(tmp, pid)
