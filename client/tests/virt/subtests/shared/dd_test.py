"""
Configurable on-guest dd test.
@author: Lukas Doktor <ldoktor@redhat.com>
@copyright: 2012 Red Hat, Inc.
"""
import logging
from autotest.client.shared import error
from autotest.client.tests.virt.aexpect import ShellCmdError
from autotest.client.tests.virt.aexpect import ShellTimeoutError


def run_dd_test(test, params, env):
    """
    Executes dd with defined parameters and checks the return number and output
    """
    def _get_file(filename, select):
        """ Picks the actual file based on select value """
        if filename == "NULL":
            return "/dev/null"
        elif filename == "ZERO":
            return "/dev/zero"
        elif filename == "RANDOM":
            return "/dev/random"
        elif filename == "URANDOM":
            return "/dev/urandom"
        else:
            # get all matching filenames
            try:
                disks = sorted(session.cmd("ls -1d %s" % filename).split('\n'))
            except ShellCmdError:   # No matching file (creating new?)
                disks = [filename]
            if disks[-1] == '':
                disks = disks[:-1]
            try:
                return disks[select]
            except IndexError:
                err = ("Incorrect cfg: dd_select out of the range (disks=%s,"
                       " select=%s)" % (disks, select))
                logging.error(err)
                raise error.TestError(err)

    vm = env.get_vm(params['main_vm'])
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    dd_if = params.get("dd_if")
    dd_if_select = int(params.get("dd_if_select", '-1'))
    dd_of = params.get("dd_of")
    dd_of_select = int(params.get("dd_of_select", '-1'))
    dd_bs = params.get("dd_bs")
    dd_count = params.get("dd_count")
    dd_iflag = params.get("dd_iflag")
    dd_oflag = params.get("dd_oflag")
    dd_skip = params.get("dd_skip")
    dd_seek = params.get("dd_seek")

    dd_timeout = int(params.get("dd_timeout", 60))

    dd_output = params.get("dd_output", "")
    dd_stat = int(params.get("dd_stat", 0))

    dd_cmd = "dd"
    if dd_if:
        dd_if = _get_file(dd_if, dd_if_select)
        dd_cmd += " if=%s" % dd_if
    if dd_of:
        dd_of = _get_file(dd_of, dd_of_select)
        dd_cmd += " of=%s" % dd_of
    if dd_bs:
        dd_cmd += " bs=%s" % dd_bs
    if dd_count:
        dd_cmd += " count=%s" % dd_count
    if dd_iflag:
        dd_cmd += " iflag=%s" % dd_iflag
    if dd_oflag:
        dd_cmd += " oflag=%s" % dd_oflag
    if dd_skip:
        dd_cmd += " skip=%s" % dd_skip
    if dd_seek:
        dd_cmd += " seek=%s" % dd_seek
    logging.info("Using '%s' cmd", dd_cmd)

    try:
        (stat, out) = session.cmd_status_output(dd_cmd, timeout=dd_timeout)
    except ShellTimeoutError:
        err = ("dd command timed-out (cmd='%s', timeout=%d)"
                                                    % (dd_cmd, dd_timeout))
        logging.error(err)
        raise error.TestFail(err)
    except ShellCmdError, details:
        stat = details.status
        out = details.output

    logging.debug("Returned dd_status: %s\nReturned output:\n%s", stat, out)
    if stat != dd_stat:
        err = ("Return code doesn't match (expected=%s, actual=%s)\n"
               "Output:\n%s" % (dd_stat, stat, out))
        logging.error(err)
        raise error.TestFail(err)
    if dd_output not in out:
        err = ("Output doesn't match:\nExpected:\n%s\nActual:\n%s"
                                                        % (dd_output, out))
        raise error.TestFail(err)
    logging.info("dd test succeeded.")
    return
