#
# Copyright 2007 Google Inc. All Rights Reserved.

"""Runs profilers on a machine when no autotest job is running.

This is used to profile a task when the task is running on a machine that is not
running through autotest.
"""

__author__ = 'cranger@google.com (Colby Ranger)'

import common
from autotest_lib.client.common_lib import barrier


def generate_test(machines, hostname, profilers, timeout_start, timeout_stop,
                        timeout_sync=180):
    control_file = []
    for profiler in profilers:
        control_file.append("job.profilers.add(%s)"
                                % str(profiler)[1:-1])  # Remove parens

    control_file.append("job.run_test('barriertest',%d,%d,%d,'%s','%s',%s)"
                    % (timeout_sync, timeout_start, timeout_stop,
                            hostname, "PROF_MASTER", str(machines)))

    for profiler in profilers:
        control_file.append("job.profilers.delete('%s')" % profiler[0])

    return "\n".join(control_file)


def wait_for_profilers(machines, timeout = 300):
    sb = barrier.barrier("PROF_MASTER", "sync_profilers",
            timeout, port=11920)
    sb.rendezvous_servers("PROF_MASTER", *machines)


def start_profilers(machines, timeout = 120):
    sb = barrier.barrier("PROF_MASTER", "start_profilers",
            timeout, port=11920)
    sb.rendezvous_servers("PROF_MASTER", *machines)


def stop_profilers(machines, timeout = 120):
    sb = barrier.barrier("PROF_MASTER", "stop_profilers",
            timeout, port=11920)
    sb.rendezvous_servers("PROF_MASTER", *machines)
